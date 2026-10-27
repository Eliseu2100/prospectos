import { httpClient } from "@/services/httpClient"

export type EstadoWhatsapp = "open" | "connecting" | "close" | "inexistente" | "indisponivel"

export interface ConfigEnvio {
  whatsapp: {
    url: string
    instancia: string
    chave_configurada: boolean
    chave_mascarada: string | null
    limite_diario: number
    enviados_hoje: number
  }
  telegram: {
    token_configurado: boolean
    token_mascarado: string | null
    chat_id: string
  }
  gemini: {
    modelo: string
    opcoes: { valor: string; rotulo: string }[]
  }
}

export interface SalvarWhatsapp {
  url: string
  instancia: string
  chave?: string
  limite_diario: number
}

export interface EnvioWhatsappResposta {
  ok: true
  status_novo: string | null
  enviados_hoje: number
  limite_diario: number
}

export const envioService = {
  obterConfig: () => httpClient.get<ConfigEnvio>("/api/envio/config"),

  salvarWhatsapp: (dados: SalvarWhatsapp) =>
    httpClient.post<{ ok: true }>("/api/envio/config/whatsapp", dados),

  salvarTelegram: (dados: { token?: string; chat_id?: string }) =>
    httpClient.post<{ ok: true }>("/api/envio/config/telegram", dados),

  salvarModeloGemini: (modelo: string) =>
    httpClient.post<{ ok: true; modelo: string }>("/api/envio/config/gemini-modelo", { modelo }),

  estadoWhatsapp: () =>
    httpClient.get<{ estado: EstadoWhatsapp; detalhe?: string }>("/api/envio/whatsapp/estado"),

  conectarWhatsapp: () =>
    httpClient.post<{ conectado: boolean; qrcode: string | null }>("/api/envio/whatsapp/conectar"),

  enviarWhatsapp: (canal: string, leadRef: string, texto: string) =>
    httpClient.post<EnvioWhatsappResposta>(
      `/api/envio/whatsapp/${canal}/${encodeURIComponent(leadRef)}`,
      { texto }
    ),

  detectarChatTelegram: () =>
    httpClient.post<{ ok: true; chat_id: string; nome: string }>("/api/envio/telegram/detectar-chat"),

  testarTelegram: () => httpClient.post<{ ok: true }>("/api/envio/telegram/teste"),

  enviarResumoTelegram: () => httpClient.post<{ ok: true }>("/api/envio/telegram/resumo"),
}
