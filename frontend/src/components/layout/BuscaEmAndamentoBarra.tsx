import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, X } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { buscaService } from "@/services/buscaService"

/** Faixa fina sob o cabeçalho, em todas as telas, enquanto uma busca no Google
 * Maps roda em segundo plano - com progresso e botão de cancelar. */
export function BuscaEmAndamentoBarra() {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ["busca-status-global"],
    queryFn: buscaService.consultarStatus,
    refetchInterval: (query) => (query.state.data?.rodando ? 2500 : 15000),
  })
  const cancelar = useMutation({
    mutationFn: buscaService.cancelar,
    onSuccess: (res) => {
      toast.success(res.mensagem)
      queryClient.invalidateQueries({ queryKey: ["busca-status-global"] })
      queryClient.invalidateQueries({ queryKey: ["busca-status"] })
    },
    onError: (erro: Error) => toast.error(erro.message),
  })

  if (!data?.rodando) return null

  const total = data.empresas_encontradas
  const feitas = data.empresas_processadas
  const percentual = data.etapa === "verificando_sites" && total > 0 ? Math.round((feitas / total) * 100) : null

  return (
    <div className="border-t border-border bg-primary/8">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-3 px-4 py-2 sm:px-6">
        <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
        <p className="min-w-0 flex-1 truncate text-[13px]">
          <span className="font-medium">Busca em andamento</span>
          <span className="text-muted-foreground">
            {" · "}
            {data.mensagem || "Buscando no Google Maps..."}
            {percentual !== null && ` (${percentual}%)`}
          </span>
        </p>
        <Button
          size="xs"
          variant="outline"
          disabled={cancelar.isPending}
          onClick={() => cancelar.mutate()}
        >
          <X className="size-3" />
          {cancelar.isPending ? "Cancelando..." : "Cancelar busca"}
        </Button>
      </div>
    </div>
  )
}
