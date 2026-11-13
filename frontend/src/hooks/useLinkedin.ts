import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  linkedinService,
  type FiltrosLinkedin,
  type NovoLeadLinkedin,
  type StatusLinkedin,
  type TipoTextoLinkedin,
} from "@/services/linkedinService"

const CHAVE_LEADS = ["linkedin-leads"]

export function useLeadsLinkedin(filtros: FiltrosLinkedin) {
  return useQuery({
    queryKey: [...CHAVE_LEADS, filtros],
    queryFn: () => linkedinService.listarLeads(filtros),
    placeholderData: (anterior) => anterior,
  })
}

export function useImportarCsvLinkedin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (csv: string) => linkedinService.importarCsv(csv),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      toast.success(`${res.importados} contato(s) importado(s), ${res.ignorados} ignorado(s).`)
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useAdicionarLeadLinkedin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (dados: NovoLeadLinkedin) => linkedinService.adicionarLead(dados),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      toast.success("Contato adicionado.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useGerarTextoLinkedin() {
  return useMutation({
    mutationFn: ({ id, tipo }: { id: number; tipo: TipoTextoLinkedin }) =>
      linkedinService.gerar(id, tipo),
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useMudarStatusLinkedin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status, texto }: { id: number; status: StatusLinkedin; texto?: string }) =>
      linkedinService.mudarStatus(id, status, texto),
    onSuccess: (_res, vars) => {
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      queryClient.invalidateQueries({ queryKey: ["linkedin-historico", vars.id] })
      toast.success("Status atualizado.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useHistoricoLinkedin(id: number | null) {
  return useQuery({
    queryKey: ["linkedin-historico", id],
    queryFn: () => linkedinService.historico(id as number),
    enabled: id !== null,
  })
}
