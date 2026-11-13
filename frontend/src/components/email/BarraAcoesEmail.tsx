import { FileSpreadsheet, Globe, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useEstadoImportacaoSites, useImportarSitesEmail } from "@/hooks/useEmail"

interface BarraAcoesEmailProps {
  onImportarReceita: () => void
  onAdicionar: () => void
}

export function BarraAcoesEmail({ onImportarReceita, onAdicionar }: BarraAcoesEmailProps) {
  const { data: estado } = useEstadoImportacaoSites(true)
  const importarSites = useImportarSitesEmail()
  const rodando = Boolean(estado?.rodando)
  const percentual =
    estado && estado.total > 0 ? Math.min(100, Math.round((estado.processados / estado.total) * 100)) : 0

  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={rodando || importarSites.isPending} onClick={() => importarSites.mutate()}>
          <Globe className="size-4" />
          {rodando ? "Buscando..." : "Buscar e-mails nos sites dos meus leads"}
        </Button>
        <Button variant="outline" onClick={onImportarReceita}>
          <FileSpreadsheet className="size-4" />
          Importar da base da Receita
        </Button>
        <Button variant="outline" onClick={onAdicionar}>
          <Plus className="size-4" />
          Adicionar e-mail
        </Button>
      </div>

      {rodando && estado && (
        <div className="space-y-1.5" role="status" aria-live="polite">
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500"
              style={{ width: `${percentual}%` }}
            />
          </div>
          <p className="text-xs tabular-nums text-muted-foreground">
            {estado.processados} de {estado.total} sites analisados · {estado.novos} e-mail(s) novo(s)
            {estado.mensagem ? ` · ${estado.mensagem}` : ""}
          </p>
        </div>
      )}
      {!rodando && estado && estado.total > 0 && estado.mensagem && (
        <p className="text-xs text-muted-foreground">
          Última busca: {estado.mensagem} ({estado.novos} novo(s)).
        </p>
      )}
    </div>
  )
}
