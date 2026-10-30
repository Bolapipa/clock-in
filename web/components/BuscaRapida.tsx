"use client";

// Busca rápida (Ctrl K ou Cmd K): procura órgãos pelo nome e leva às páginas do site.
// A lista de órgãos só é baixada na primeira vez que a busca abre.
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { ArrowUpRight, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useLingua } from "@/components/Provedores";
import { usarListaDeOrgaos } from "@/lib/cliente";
import { formatarPercentual, linkDoOrgao, nomeLegivel, normalizar } from "@/lib/dados";

const EVENTO = "clockin:abrir-busca";

// Qualquer botão do site abre a busca disparando este evento
export function abrirBusca() {
  window.dispatchEvent(new Event(EVENTO));
}

export function BuscaRapida() {
  const { t } = useLingua();
  const router = useRouter();
  const [aberta, setAberta] = useState(false);
  const [carregar, setCarregar] = useState(false);
  const lista = usarListaDeOrgaos(carregar);

  useEffect(() => {
    const abrir = () => { setCarregar(true); setAberta(true); };
    const atalho = (evento: KeyboardEvent) => {
      if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === "k") {
        evento.preventDefault();
        setCarregar(true);
        setAberta((atual) => !atual);
      }
    };
    window.addEventListener(EVENTO, abrir);
    window.addEventListener("keydown", atalho);
    return () => { window.removeEventListener(EVENTO, abrir); window.removeEventListener("keydown", atalho); };
  }, []);

  const ir = (href: string) => { setAberta(false); router.push(href); };
  const paginas = [
    { href: "/#panorama", texto: t.nav.panorama },
    { href: "/metodologia/", texto: t.nav.metodologia },
    { href: "/desenvolvedores/", texto: t.nav.desenvolvedores },
  ];

  return (
    <Dialog.Root open={aberta} onOpenChange={setAberta}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-[12vh] z-50 w-[min(40rem,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-2xl border border-linha bg-superficie shadow-2xl">
          <Dialog.Title className="so-leitor">{t.nav.buscar}</Dialog.Title>
          <Dialog.Description className="so-leitor">{t.busca.dica}</Dialog.Description>
          {/* O filtro do cmdk ignora acentos e maiúsculas, como a busca da lista */}
          <Command label={t.nav.buscar} filter={(valor, busca) => (normalizar(valor).includes(normalizar(busca).trim()) ? 1 : 0)}>
            <div className="flex items-center gap-3 border-b border-linha px-4">
              <Search className="size-4 text-tinta-3" />
              <Command.Input autoFocus placeholder={t.busca.placeholder}
                className="h-14 w-full bg-transparent text-base text-tinta outline-none placeholder:text-tinta-3" />
              <kbd className="rounded border border-linha px-1.5 font-mono text-[0.68rem] text-tinta-3">Esc</kbd>
            </div>
            <Command.List className="max-h-[min(26rem,60vh)] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-8 text-center text-sm text-tinta-3">
                {lista.estado === "carregando" ? t.comum.carregando : t.busca.vazio}
              </Command.Empty>
              <Command.Group heading={t.busca.paginas} className="px-1 pb-2 text-xs text-tinta-3 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:font-mono">
                {paginas.map((pagina) => (
                  <Command.Item key={pagina.href} value={pagina.texto} onSelect={() => ir(pagina.href)}
                    className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm text-tinta aria-selected:bg-superficie-2">
                    {pagina.texto}<ArrowUpRight className="size-4 text-tinta-3" />
                  </Command.Item>
                ))}
              </Command.Group>
              {lista.estado === "pronto" && (
                <Command.Group heading={t.busca.orgaos} className="px-1 text-xs text-tinta-3 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:font-mono">
                  {lista.dados.orgaos.map((orgao) => (
                    <Command.Item key={orgao.slug} value={`${nomeLegivel(orgao.nome)} ${orgao.nome}`} onSelect={() => ir(linkDoOrgao(orgao.slug))}
                      className="flex cursor-pointer items-center justify-between gap-4 rounded-lg px-3 py-2.5 text-sm text-tinta aria-selected:bg-superficie-2">
                      <span className="truncate">{nomeLegivel(orgao.nome)}</span>
                      <span className="shrink-0 font-mono text-xs text-tinta-3 numeros">{formatarPercentual(orgao.percentual_ok)}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
            </Command.List>
            <div className="border-t border-linha px-4 py-2.5 font-mono text-[0.7rem] text-tinta-3">{t.busca.dica}</div>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
