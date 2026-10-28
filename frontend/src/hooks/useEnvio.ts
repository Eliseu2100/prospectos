import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { useInvalidarLeads } from "@/hooks/useInvalidarLeads"
import { envioService, type SalvarWhatsapp } from "@/services/envioService"

const CHAVE_CONFIG = ["envio-config"]
const CHAVE_ESTADO = ["whatsapp-estado"]

export function useConfigEnvio() {
  return useQuery({ queryKey: CHAVE_CONFIG, queryFn: envioService.obterConfig })
}

/** Estado da conexão do WhatsApp na Evolution API. Enquanto o QR code está na
 * tela, o card passa `rapido` pra detectar o "conectou" sem o usuário recarregar. */
export function useEstadoWhatsapp(rapido = false) {
  return useQuery({
    queryKey: CHAVE_ESTADO,
    queryFn: envioService.estadoWhatsapp,
    refetchInterval: rapido ? 3000 : 30000,
  })
}

function useMutacaoComToast<TArgs, TRes>(
  fn: (args: TArgs) => Promise<TRes>,
  sucesso: string | ((res: TRes) => string),
  invalidar: string[][] = [CHAVE_CONFIG]
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (res) => {
      invalidar.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }))
      toast.success(typeof sucesso === "function" ? sucesso(res) : sucesso)
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useSalvarWhatsapp() {
  return useMutacaoComToast(
    (dados: SalvarWhatsapp) => envioService.salvarWhatsapp(dados),
    "Configuração do WhatsApp salva.",
    [CHAVE_CONFIG, CHAVE_ESTADO]
  )
}

export function useConectarWhatsapp() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: envioService.conectarWhatsapp,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: CHAVE_ESTADO })
      if (res.conectado) toast.success("WhatsApp já está conectado.")
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useSalvarTelegram() {
  return useMutacaoComToast(
    (dados: { token?: string; chat_id?: string }) => envioService.salvarTelegram(dados),
    "Configuração do Telegram salva."
  )
}

export function useDetectarChatTelegram() {
  return useMutacaoComToast(
    () => envioService.detectarChatTelegram(),
    (res) => `Chat detectado${res.nome ? `: ${res.nome}` : ""}.`
  )
}

export function useTestarTelegram() {
  return useMutacaoComToast(() => envioService.testarTelegram(), "Mensagem de teste enviada.", [])
}

export function useEnviarResumoTelegram() {
  return useMutacaoComToast(
    () => envioService.enviarResumoTelegram(),
    "Resumo do dia enviado pro seu Telegram.",
    []
  )
}

export function useSalvarModeloGemini() {
  return useMutacaoComToast(
    (modelo: string) => envioService.salvarModeloGemini(modelo),
    "Modelo do Gemini atualizado."
  )
}

export function useEnviarWhatsapp(canal: string, leadRef: string) {
  const queryClient = useQueryClient()
  const invalidarLeads = useInvalidarLeads()
  return useMutation({
    mutationFn: (texto: string) => envioService.enviarWhatsapp(canal, leadRef, texto),
    onSuccess: (res) => {
      invalidarLeads()
      queryClient.invalidateQueries({ queryKey: ["conversa", canal, leadRef] })
      queryClient.invalidateQueries({ queryKey: ["whatsapp-caixa"] })
      queryClient.invalidateQueries({ queryKey: CHAVE_CONFIG })
      toast.success(
        `Mensagem enviada pelo WhatsApp (${res.enviados_hoje}/${res.limite_diario} hoje)` +
          (res.status_novo ? " · lead marcado como contatado." : ".")
      )
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

/** true quando a Evolution API está com o WhatsApp conectado - aí as conversas
 * acontecem dentro do app em vez de abrir o WhatsApp Web por fora. */
export function useWhatsappConectado() {
  const { data } = useEstadoWhatsapp()
  return data?.estado === "open"
}

/** Com a conversa aberta na tela, puxa as mensagens novas desse lead da
 * Evolution a cada poucos segundos e atualiza o histórico. */
export function useSincronizarLead(placeId: string, ativo: boolean) {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: ["whatsapp-sync-lead", placeId],
    queryFn: async () => {
      const res = await envioService.sincronizarLead(placeId)
      if (res.novas > 0) {
        queryClient.invalidateQueries({ queryKey: ["conversa", "maps", placeId] })
        queryClient.invalidateQueries({ queryKey: ["lead", placeId] })
        queryClient.invalidateQueries({ queryKey: ["whatsapp-caixa"] })
      }
      return res
    },
    enabled: ativo && Boolean(placeId),
    refetchInterval: 8000,
    refetchIntervalInBackground: true,
  })
}

export function useCaixaWhatsapp() {
  return useQuery({
    queryKey: ["whatsapp-caixa"],
    queryFn: envioService.caixa,
    refetchInterval: 15000,
  })
}

export function useSincronizarTodos() {
  const queryClient = useQueryClient()
  const invalidarLeads = useInvalidarLeads()
  return useMutation({
    mutationFn: envioService.sincronizarTodos,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["whatsapp-caixa"] })
      invalidarLeads()
      toast.success(
        res.novas ? `${res.novas} mensagem(ns) nova(s) do WhatsApp.` : "Tudo em dia, nenhuma mensagem nova."
      )
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useSalvarAvisos() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (numero: string) => envioService.salvarAvisos(numero),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: CHAVE_CONFIG })
      if (res.mesmo_numero_conectado) {
        toast.warning(
          "Esse é o mesmo número conectado no Seriax OS. O WhatsApp não toca para mensagens que você manda para você mesmo: use outro número ou o Telegram.",
          { duration: 10000 }
        )
      } else {
        toast.success(res.whatsapp_numero ? "Número de aviso salvo." : "Aviso por WhatsApp desligado.")
      }
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}

export function useTestarAviso() {
  return useMutacaoComToast(
    () => envioService.testarAviso(),
    (res) => `Aviso de teste enviado por: ${res.canais.join(" e ")}.`,
    []
  )
}
