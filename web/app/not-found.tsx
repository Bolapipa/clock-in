// Página não encontrada
import Link from "next/link";

import { IconeRelogio } from "@/components/Marca";

export default function NaoEncontrada() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-32 text-center">
      <IconeRelogio className="size-14 text-tinta-3" />
      <p className="mt-6 font-mono text-sm text-tinta-3">404</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-tinta">Este endereço não bateu o ponto.</h1>
      <p className="mt-3 text-tinta-2">A página não existe ou mudou de lugar.</p>
      <Link href="/" className="mt-8 inline-flex h-11 items-center rounded-full bg-tinta px-5 text-sm font-medium text-fundo">Voltar ao início</Link>
    </div>
  );
}
