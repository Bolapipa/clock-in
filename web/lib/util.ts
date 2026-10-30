// Junta classes do Tailwind sem conflito (a última vence), no padrão do shadcn/ui
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...classes: ClassValue[]) {
  return twMerge(clsx(classes));
}
