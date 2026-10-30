// Marca do Clock-in: um relógio com o ponteiro batendo o ponto (o ponto âmbar) e o nome ao lado
import { cn } from "@/lib/util";

export function IconeRelogio({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn("size-7", className)}>
      <circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="2.6" />
      {/* Marcas das 12, 3, 6 e 9 horas */}
      {[0, 90, 180, 270].map((graus) => (
        <line key={graus} x1="16" y1="5.5" x2="16" y2="8" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"
          transform={`rotate(${graus} 16 16)`} />
      ))}
      <path d="M16 16 L16 10" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M16 16 L21 19.5" stroke="var(--ambar)" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="16" cy="16" r="2.2" fill="var(--ambar)" />
    </svg>
  );
}

// Ícone do GitHub (o Lucide 1.x não traz mais ícones de marcas)
export function IconeGithub({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={cn("size-4", className)} fill="currentColor">
      <path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.56-.29-5.25-1.28-5.25-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.78 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.77.11 3.06.74.8 1.19 1.83 1.19 3.09 0 4.42-2.7 5.39-5.27 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

export function Marca({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-tinta", className)}>
      <IconeRelogio />
      <span className="text-[1.2rem] font-semibold tracking-[-0.03em]">
        clock<span className="text-ambar">-</span>in
      </span>
    </span>
  );
}
