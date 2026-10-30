// Página "Como medimos"
import type { Metadata } from "next";

import { Metodologia } from "@/components/textos/Metodologia";

export const metadata: Metadata = {
  title: "Como medimos",
  description: "As regras do Clock-in: quando um link é quebrado, o que conta como falha, cobertura, status das bases e prazos por periodicidade.",
};

export default function Pagina() {
  return <Metodologia />;
}
