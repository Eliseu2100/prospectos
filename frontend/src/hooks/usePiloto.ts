import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { useInvalidarLeads } from "@/hooks/useInvalidarLeads"
import { pilotoService, type SalvarConfigPiloto } from "@/services/pilotoService"

const CHAVE = ["piloto"]

/** Painel do piloto - atualiza sozinho enquanto a tela está aberta (o piloto
 * age em segundo plano, então a atividade muda sem o usuário fazer nada). */
export function usePainelPiloto() {
  return useQuery({ queryKey: CHAVE, queryFn: pilotoService.painel, refetchInterval: 10000 })
}

function useAcaoPiloto<TArgs, TRes>(fn: (args: TArgs) => Promise<TRes>, sucesso?: (res: TRes) => string) {
  const queryClient = useQueryClient()
  const invalidarLeads = useInvalidarLeads()
  return useMutation({
    mutationFn: fn,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: CHAVE })
      queryClient.invalidateQueries({ queryKey: ["whatsapp-caixa"] })
      invalidarLeads()
      if (sucesso) toast.success(sucesso(res))
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useSalvarConfigPiloto() {
  return useAcaoPiloto((dados: SalvarConfigPiloto) => pilotoService.salvarConfig(dados), () => "Configuração do piloto salva.")
}

export function useAtivarPiloto() {
  return useAcaoPiloto(
    (ativo: boolean) => pilotoService.ativar(ativo),
    (res) => (res.ativo ? "Piloto ligado. O primeiro contato sai em instantes." : "Piloto pausado.")
  )
}

export function useEnviarProximo() {
  return useAcaoPiloto(() => pilotoService.enviarProximo(), (res) => `Mensagem enviada para ${res.nome}.`)
}

export function useAssumirConversa() {
  return useAcaoPiloto((placeId: string) => pilotoService.assumir(placeId), () => "Você assumiu a conversa.")
}

export function useDevolverAoPiloto() {
  return useAcaoPiloto((placeId: string) => pilotoService.devolver(placeId), () => "Conversa devolvida ao piloto.")
}
