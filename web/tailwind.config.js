// Tailwind: as cores apontam para variáveis CSS (src/index.css), que mudam sozinhas no tema escuro
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        papel: "var(--papel)",
        superficie: "var(--superficie)",
        tinta: "var(--tinta)",
        "tinta-suave": "var(--tinta-suave)",
        linha: "var(--linha)",
        "linha-forte": "var(--linha-forte)",
        carimbo: "var(--carimbo)",
        "carimbo-fundo": "var(--carimbo-fundo)",
        "carimbo-texto": "var(--carimbo-texto)",
        bom: "var(--bom)",
        "bom-texto": "var(--bom-texto)",
        "bom-fundo": "var(--bom-fundo)",
        atencao: "var(--atencao)",
        "atencao-texto": "var(--atencao-texto)",
        "atencao-fundo": "var(--atencao-fundo)",
        ruim: "var(--ruim)",
        "ruim-texto": "var(--ruim-texto)",
        "ruim-fundo": "var(--ruim-fundo)",
        "neutro-fundo": "var(--neutro-fundo)",
        faixa: "var(--faixa)",
        "faixa-texto": "var(--faixa-texto)",
      },
      fontFamily: {
        sans: ["Archivo", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "Cascadia Code", "Consolas", "monospace"],
      },
      maxWidth: {
        miolo: "1180px",
      },
    },
  },
  plugins: [],
};
