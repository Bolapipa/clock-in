// Imagem de compartilhamento (aparece quando o link é colado no LinkedIn, WhatsApp, Slack...).
// Gerada uma vez no build, com os números do dia: por isso muda sozinha a cada publicação.
import { ImageResponse } from "next/og";

import { formatarNumero, formatarPercentual, partesDaRegua } from "@/lib/dados";
import { dataNaLingua } from "@/lib/i18n";
import { lerResumo } from "@/lib/servidor";

export const dynamic = "force-static";
export const alt = "Clock-in: os dados abertos do Brasil ainda batem o ponto?";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const COR = { ok: "#34d399", observacao: "#fbbf24", quebrados: "#f87171", nao_testados: "#5f6b7d" } as const;

export default async function Imagem() {
  const resumo = await lerResumo();
  const links = resumo?.links;
  const partes = links ? partesDaRegua({ total: links.total, ok: links.ok, emObservacao: links.em_observacao, quebrados: links.quebrados }) : [];

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 64,
        background: "#06080d", color: "#e9eef6", fontFamily: "sans-serif" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ display: "flex", width: 44, height: 44, borderRadius: 22, border: "5px solid #e9eef6", position: "relative" }}>
            <div style={{ position: "absolute", left: 17, top: 6, width: 5, height: 14, background: "#e9eef6", borderRadius: 3 }} />
            <div style={{ position: "absolute", left: 17, top: 17, width: 14, height: 5, background: "#ffb23f", borderRadius: 3 }} />
          </div>
          <div style={{ display: "flex", fontSize: 40, fontWeight: 700, letterSpacing: -1 }}>
            clock<span style={{ color: "#ffb23f" }}>-</span>in
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 40, color: "#a3aebf" }}>Os dados abertos do Brasil ainda batem o ponto?</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 28, marginTop: 8 }}>
            <div style={{ display: "flex", fontSize: 200, fontWeight: 800, letterSpacing: -8, lineHeight: 1 }}>{formatarPercentual(links?.percentual_ok)}</div>
            <div style={{ display: "flex", flexDirection: "column", fontSize: 36, lineHeight: 1.25, paddingBottom: 26, color: "#e9eef6" }}>
              <span>dos links testados</span>
              <span>respondem bem</span>
            </div>
          </div>
          {links && (
            <div style={{ display: "flex", marginTop: 34, width: "100%", height: 22, gap: 4 }}>
              {partes.filter((parte) => parte.quantidade > 0).map((parte) => (
                <div key={parte.chave} style={{ display: "flex", flex: parte.quantidade, background: COR[parte.chave], borderRadius: 11 }} />
              ))}
            </div>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 28, color: "#a3aebf" }}>
          <div style={{ display: "flex", gap: 36 }}>
            <span>{formatarNumero(resumo?.orgaos)} órgãos</span>
            <span style={{ color: "#f87171" }}>{formatarNumero(links?.quebrados)} links quebrados</span>
          </div>
          <span>{resumo ? `dados.gov.br · ${dataNaLingua(resumo.data_coleta, "pt")}` : "dados.gov.br"}</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
