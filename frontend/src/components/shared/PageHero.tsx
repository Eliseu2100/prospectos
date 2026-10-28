import { cn } from "@/lib/utils"

interface PageHeroProps {
  icone: React.ReactNode
  titulo: string
  descricao: string
  /** Classes do gradiente do ícone (ex.: "from-google-maps-start via-google-maps-mid to-google-maps-end").
   * A cor do canal fica só no ícone - a superfície continua neutra. */
  gradiente: string
  acoes?: React.ReactNode
}

/** Abertura de cada área do produto: cartão branco, título grande e respiro
 * generoso. Mesmo layout em todas as páginas, mudando só o ícone do canal. */
export function PageHero({ icone, titulo, descricao, gradiente, acoes }: PageHeroProps) {
  return (
    <div className="flex flex-col gap-5 rounded-[28px] bg-card px-6 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-8 sm:py-7">
      <div className="flex items-center gap-4">
        <div
          className={cn(
            "flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white",
            gradiente
          )}
        >
          {icone}
        </div>
        <div className="min-w-0">
          <h2 className="text-2xl font-semibold tracking-tight sm:text-[28px] sm:leading-tight">{titulo}</h2>
          <p className="text-[15px] text-muted-foreground">{descricao}</p>
        </div>
      </div>

      {acoes && <div className="flex shrink-0 flex-wrap items-center gap-2">{acoes}</div>}
    </div>
  )
}

/** Classe dos links de ação do PageHero (pílula neutra). */
export const CLASSE_ACAO_HERO =
  "inline-flex h-9 items-center gap-1.5 rounded-full bg-secondary px-4 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
