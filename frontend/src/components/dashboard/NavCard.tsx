import { Link } from "react-router-dom"
import { ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface NavCardProps {
  to: string
  titulo: string
  descricao: string
  icone: React.ReactNode
  destaqueInstagram?: boolean
}

export function NavCard({
  to,
  titulo,
  descricao,
  icone,
  destaqueInstagram = false,
}: NavCardProps) {
  return (
    <Link
      to={to}
      className={cn(
        "group flex items-center gap-3 rounded-2xl bg-card p-4 transition-colors hover:bg-accent/40",
        destaqueInstagram &&
          "bg-gradient-to-br from-instagram-start/[0.06] via-card to-instagram-end/[0.06] hover:from-instagram-start/[0.1] hover:to-instagram-end/[0.1]"
      )}
    >
      <div
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary",
          destaqueInstagram && "bg-transparent text-instagram-mid"
        )}
      >
        {icone}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{titulo}</p>
        <p className="line-clamp-2 text-xs text-muted-foreground">{descricao}</p>
      </div>
      <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </Link>
  )
}
