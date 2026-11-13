import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"

interface PaginacaoSimplesProps {
  pagina: number
  porPagina: number
  total: number
  onChange: (pagina: number) => void
}

export function PaginacaoSimples({ pagina, porPagina, total, onChange }: PaginacaoSimplesProps) {
  const totalPaginas = Math.max(1, Math.ceil(total / porPagina))
  if (totalPaginas <= 1) return null

  return (
    <div className="flex items-center justify-between gap-3 pt-1 text-sm text-muted-foreground">
      <span className="tabular-nums">
        Página {pagina} de {totalPaginas} · {total} no total
      </span>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={pagina <= 1} onClick={() => onChange(pagina - 1)}>
          <ChevronLeft className="size-4" />
          Anterior
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={pagina >= totalPaginas}
          onClick={() => onChange(pagina + 1)}
        >
          Próxima
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  )
}
