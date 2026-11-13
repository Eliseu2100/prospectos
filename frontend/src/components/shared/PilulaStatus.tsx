import { cn } from "@/lib/utils"

export type TomPilula = "neutro" | "azul" | "verde" | "ambar" | "vermelho"

const CLASSES_TOM: Record<TomPilula, string> = {
  neutro: "bg-muted text-muted-foreground",
  azul: "bg-primary/12 text-primary",
  verde: "bg-success/15 text-success",
  ambar: "bg-warning/15 text-warning-foreground",
  vermelho: "bg-destructive/10 text-destructive",
}

/** Pílula de status genérica (e-mail e LinkedIn). O StatusBadge dos leads do
 * Maps é amarrado aos status de lá, então este recebe rótulo e tom por fora. */
export function PilulaStatus({
  rotulo,
  tom = "neutro",
  className,
}: {
  rotulo: string
  tom?: TomPilula
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex h-5.5 items-center whitespace-nowrap rounded-full px-2.5 text-xs font-medium",
        CLASSES_TOM[tom],
        className
      )}
    >
      {rotulo}
    </span>
  )
}
