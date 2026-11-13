import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  emailService,
  type FiltrosEmail,
  type ImportarReceita,
  type NovoLeadEmail,
  type SalvarSmtp,
  type StatusEmail,
} from "@/services/emailService"

const CHAVE_CONFIG = ["email-config"]
const CHAVE_LEADS = ["email-leads"]
const CHAVE_IMPORTACAO = ["email-importacao-sites"]
const CHAVE_DESCADASTROS = ["email-descadastros"]

export function useConfigEmail() {
  return useQuery({ queryKey: CHAVE_CONFIG, queryFn: emailService.obterConfig })
}

export function useSalvarConfigEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (dados: SalvarSmtp) => emailService.salvarConfig(dados),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAVE_CONFIG })
      toast.success("Configuração de e-mail salva.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useTestarConfigEmail() {
  return useMutation({
    mutationFn: (para: string) => emailService.testarConfig(para),
    onSuccess: () => toast.success("E-mail de teste enviado. Confira a caixa de entrada."),
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useLeadsEmail(filtros: FiltrosEmail) {
  return useQuery({
    queryKey: [...CHAVE_LEADS, filtros],
    queryFn: () => emailService.listarLeads(filtros),
    placeholderData: (anterior) => anterior,
  })
}

/** Estado da busca de e-mails nos sites. Faz polling a cada 2s só enquanto roda. */
export function useEstadoImportacaoSites(ativo: boolean) {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: CHAVE_IMPORTACAO,
    queryFn: async () => {
      const estado = await emailService.estadoImportacaoSites()
      if (!estado.rodando) queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      return estado
    },
    enabled: ativo,
    refetchInterval: (consulta) => (consulta.state.data?.rodando ? 2000 : false),
  })
}

export function useImportarSitesEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: emailService.importarSites,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAVE_IMPORTACAO })
      toast.success("Busca iniciada em segundo plano.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useImportarReceita() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (dados: ImportarReceita) => emailService.importarReceita(dados),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      toast.success(`${res.importados} e-mail(s) importado(s), ${res.ignorados} ignorado(s).`)
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useAdicionarLeadEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (dados: NovoLeadEmail) => emailService.adicionarLead(dados),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      toast.success("E-mail adicionado.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useGerarEmail() {
  return useMutation({
    mutationFn: (id: number) => emailService.gerar(id),
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useEnviarEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, assunto, corpo }: { id: number; assunto: string; corpo: string }) =>
      emailService.enviar(id, { assunto, corpo }),
    onSuccess: (_res, vars) => {
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      queryClient.invalidateQueries({ queryKey: CHAVE_CONFIG })
      queryClient.invalidateQueries({ queryKey: ["email-historico", vars.id] })
      toast.success("E-mail enviado.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useMudarStatusEmail() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: StatusEmail }) =>
      emailService.mudarStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      toast.success("Status atualizado.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useHistoricoEmail(id: number | null) {
  return useQuery({
    queryKey: ["email-historico", id],
    queryFn: () => emailService.historico(id as number),
    enabled: id !== null,
  })
}

export function useDescadastros(ativo: boolean) {
  return useQuery({
    queryKey: CHAVE_DESCADASTROS,
    queryFn: emailService.listarDescadastros,
    enabled: ativo,
  })
}

export function useAdicionarDescadastro() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (email: string) => emailService.adicionarDescadastro(email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAVE_DESCADASTROS })
      queryClient.invalidateQueries({ queryKey: CHAVE_LEADS })
      toast.success("E-mail adicionado à lista de descadastros.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}
