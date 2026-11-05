import { cn } from "@/lib/utils"

// Chip de ícone por cartão, no estilo "um tom por métrica" - como o StatTile
// não tem muito espaço, cada variante usa só a cor do fundo/ícone, nunca o
// valor (esse continua neutro, exceto destaque/alerta). "azul" e "ciano" vêm
// da própria marca (identidade/design-guide.md); "instagram"/"maps" tomam
// emprestada a cor do canal (não é cor de marca, é identificação de origem).
type Variante =
  | "default"
  | "destaque"
  | "alerta"
  | "azul"
  | "ciano"
  | "instagram"
  | "maps"

interface StatTileProps {
  rotulo: string
  valor: string | number
  icone?: React.ReactNode
  variante?: Variante
}

const CHIP_POR_VARIANTE: Record<Variante, string> = {
  default: "bg-muted text-muted-foreground",
  destaque: "bg-success/12 text-success",
  alerta: "bg-warning/12 text-warning",
  azul: "bg-primary/12 text-primary",
  ciano: "bg-[var(--chart-3)]/15 text-[var(--chart-3)]",
  instagram: "bg-[var(--instagram-mid)]/14 text-[var(--instagram-mid)]",
  maps: "bg-[var(--google-maps-mid)]/14 text-[var(--google-maps-mid)]",
}

export function StatTile({ rotulo, valor, icone, variante = "default" }: StatTileProps) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-card px-4 py-3.5 transition-colors hover:bg-accent/30">
      {icone && (
        <div
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-full",
            CHIP_POR_VARIANTE[variante]
          )}
        >
          {icone}
        </div>
      )}
      <div className="min-w-0">
        <p className="truncate text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {rotulo}
        </p>
        <p
          className={cn(
            "text-2xl font-semibold leading-tight tracking-tight tabular-nums",
            variante === "destaque" && "text-success",
            variante === "alerta" && "text-warning"
          )}
        >
          {valor}
        </p>
      </div>
    </div>
  )
}
