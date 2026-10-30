// Régua de saúde dos links: barra com as quatro partes, marcas de relógio e legenda explicada
import { formatarNumero, formatarPercentual, type ChaveDaParte, type ParteDaRegua } from "../lib/dados";

// Cor de cada parte (a parte "não deu para testar" é hachurada, sem cor)
const COR_DA_PARTE: Record<ChaveDaParte, string> = {
  ok: "bg-bom",
  observacao: "bg-atencao",
  quebrados: "bg-ruim",
  nao_testados: "hachurado",
};

// 60 "minutos", com uma marca maior a cada 5 ("horas")
function MarcasDeRelogio() {
  const minutos = Array.from({ length: 61 }, (_, minuto) => minuto);
  return (
    <svg aria-hidden="true" className="mt-1.5 block h-3.5 w-full overflow-visible text-tinta-suave">
      {minutos.map((minuto) => {
        const hora = minuto % 5 === 0;
        const x = `${(minuto / 60) * 100}%`;
        return <line key={minuto} x1={x} x2={x} y1="0" y2={hora ? 14 : 7} stroke="currentColor" strokeWidth={hora ? 2 : 1} />;
      })}
    </svg>
  );
}

export function Regua({ partes, rotulo = "Links" }: { partes: ParteDaRegua[]; rotulo?: string }) {
  const descricao = partes.map((parte) => `${formatarNumero(parte.quantidade)} ${parte.rotulo}`).join(", ");
  return (
    <div>
      <div role="group" aria-label={`${rotulo}: ${descricao}`} className="regua-interativa flex h-10 gap-[3px] sm:h-12">
        {partes.filter((parte) => parte.quantidade > 0).map((parte) => (
          <span key={parte.chave} className={`parte-crescendo min-w-1 rounded ${COR_DA_PARTE[parte.chave]}`}
            style={{ flex: `${parte.quantidade} 1 0` }} title={`${formatarNumero(parte.quantidade)} ${parte.rotulo} · ${formatarPercentual(parte.percentual)}`}
          />
        ))}
      </div>
      <MarcasDeRelogio />
      <ul className="m-0 mt-5 grid list-none grid-cols-1 gap-x-7 gap-y-4 p-0 text-[0.95rem] text-tinta-suave sm:grid-cols-2 lg:grid-cols-4">
        {partes.map((parte) => (
          <li key={parte.chave} className="flex items-start gap-2.5">
            <span aria-hidden="true" className={`mt-1.5 size-3.5 flex-none rounded-sm ${COR_DA_PARTE[parte.chave]}`} />
            <span>
              <strong className="font-bold tabular-nums text-tinta">{formatarNumero(parte.quantidade)}</strong> {parte.rotulo}
              <small className="mt-0.5 block text-[0.85rem] leading-snug">
                {formatarPercentual(parte.percentual)} dos links. {parte.descricao}
              </small>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Régua pequena das listas: só o que foi testado; tracejada quando há poucos links testados
export function ReguaMini({ partes, semPercentual }: { partes: ParteDaRegua[]; semPercentual: boolean }) {
  const testadas = partes.filter((parte) => parte.chave !== "nao_testados" && parte.quantidade > 0);
  if (semPercentual || testadas.length === 0) return <span aria-hidden="true" className="hachurado inline-block h-2 w-14 rounded-sm align-middle" />;
  return (
    <span aria-hidden="true" className="inline-flex h-2 w-14 gap-px align-middle">
      {testadas.map((parte) => (
        <span key={parte.chave} className={`min-w-px rounded-sm ${COR_DA_PARTE[parte.chave]}`} style={{ flex: `${parte.quantidade} 1 0` }} />
      ))}
    </span>
  );
}
