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
      queryClient.invalidateQueries({ queryKey: CHAVE_CONFIG })
      toast.success(
        `Mensagem enviada pelo WhatsApp (${res.enviados_hoje}/${res.limite_diario} hoje)` +
          (res.status_novo ? " · lead marcado como contatado." : ".")
      )
    },
    onError: (erro: Error) => toast.error(erro.message),
  })
}
