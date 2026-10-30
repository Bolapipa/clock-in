"use client";

// Painel lateral com o detalhe de uma base: status e motivo, saúde dos links e o link para o dados.gov.br
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

import { useLingua } from "@/components/Provedores";
import { COR_DO_ESTADO, Regua, Status } from "@/components/ui";
import { formatarNumero, formatarPercentual, partesDaRegua, primeiraMaiuscula, type Base } from "@/lib/dados";
import { cn } from "@/lib/util";

const URL_DO_PORTAL = "https://dados.gov.br/dados/conjuntos-dados/";

export function PainelDaBase({ aberto, base, carregando, aoFechar }: { aberto: boolean; base: Base | null; carregando: boolean; aoFechar: () => void }) {
  const { t } = useLingua();
  const partes = base ? partesDaRegua({ total: base.links_total, ok: base.links_ok, emObservacao: base.links_em_observacao, quebrados: base.links_quebrados }) : [];

  return (
    <Dialog.Root open={aberto} onOpenChange={(abrir) => { if (!abrir) aoFechar(); }}>
      <AnimatePresence>
        {aberto && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild forceMount>
              <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 320, damping: 34 }}
                className="fixed inset-y-0 right-0 z-50 flex w-[min(34rem,100vw)] flex-col overflow-y-auto border-l border-linha bg-fundo shadow-2xl">
                <div className="sticky top-0 flex items-center justify-between border-b border-linha bg-fundo/90 px-6 py-4 backdrop-blur">
                  <span className="font-mono text-xs text-tinta-3">{t.base.titulo}</span>
                  <Dialog.Close aria-label={t.nav.fechar} className="grid size-9 place-items-center rounded-full border border-linha text-tinta-2 hover:text-tinta">
                    <X className="size-4" />
                  </Dialog.Close>
                </div>

                {!base ? (
                  <div className="p-6">
                    <Dialog.Title className="text-xl font-semibold text-tinta">{carregando ? t.orgao.carregando : t.base.naoEncontrada}</Dialog.Title>
                    <Dialog.Description className="so-leitor">{t.base.titulo}</Dialog.Description>
                  </div>
                ) : (
                  <div className="flex flex-col gap-8 p-6">
                    <div>
                      <Dialog.Title className="text-2xl font-semibold leading-tight tracking-[-0.03em] text-tinta">{base.titulo || base.slug}</Dialog.Title>
                      <Dialog.Description className="mt-2 text-sm text-tinta-2">
                        {t.orgao.periodicidade(t.periodicidades[base.periodicidade] ?? base.periodicidade)}
                      </Dialog.Description>
                    </div>

                    <div className="rounded-2xl border border-linha bg-superficie p-5">
                      <p className="font-mono text-xs text-tinta-3">{t.base.status}</p>
                      <div className="mt-3"><Status status={base.status} grande /></div>
                      <p className="mt-4 text-lg leading-snug text-tinta">
                        {primeiraMaiuscula(base.motivo ?? (base.fora_do_ar ? t.statusExplicacao.FORA_DO_AR : t.base.semMotivo))}
                      </p>
                      <p className="mt-2 text-sm leading-relaxed text-tinta-2">{t.statusExplicacao[base.status] ?? ""}</p>
                    </div>

                    <div>
                      <p className="mb-3 text-sm font-medium text-tinta">{t.base.links}</p>
                      <Regua partes={partes} rotulo={t.base.links} altura="h-3" />
                      <dl className="mt-4 grid grid-cols-2 gap-3">
                        <div className="rounded-xl border border-linha bg-superficie p-3">
                          <dt className="text-xs text-tinta-3">{t.base.cadastrados}</dt>
                          <dd className="numeros mt-1 text-xl font-semibold text-tinta">{formatarNumero(base.links_total)}</dd>
                        </div>
                        <div className="rounded-xl border border-linha bg-superficie p-3">
                          <dt className="text-xs text-tinta-3">{t.base.testados}</dt>
                          <dd className="numeros mt-1 text-xl font-semibold text-tinta">{formatarNumero(base.links_testados)}</dd>
                        </div>
                      </dl>
                      <ul className="mt-4 space-y-2 text-sm">
                        {partes.map((parte) => (
                          <li key={parte.chave} className="flex items-center justify-between gap-3">
                            <span className="flex items-center gap-2 text-tinta-2">
                              <span aria-hidden="true" className={cn("size-2.5 rounded-full", COR_DO_ESTADO[parte.chave])} />{t.estados[parte.chave]}
                            </span>
                            <span className="numeros font-mono text-xs text-tinta">{formatarNumero(parte.quantidade)} · {formatarPercentual(parte.percentual)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <a href={URL_DO_PORTAL + encodeURIComponent(base.slug)} target="_blank" rel="noopener"
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-tinta px-5 text-sm font-medium text-fundo transition hover:bg-tinta/85">
                      {t.base.portal}<ArrowUpRight className="size-4" />
                    </a>
                  </div>
                )}
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
