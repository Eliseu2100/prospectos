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
  avisos: {
    whatsapp_numero: string
    telegram_pronto: boolean
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

export interface ConversaCaixa {
  place_id: string
  nome: string
  telefone: string | null
  status: string
  nicho: string | null
  ultimo_autor: "lead" | "vendedor"
  ultimo_texto: string
  ultima_em: string
  aguardando_voce: boolean
  ja_respondeu: boolean
}

export interface CaixaWhatsapp {
  conversas: ConversaCaixa[]
  sincronizacao: { ultima_em: string | null; novas: number; erro: string | null }
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

  sincronizarTodos: () =>
    httpClient.post<{ ok: true; novas: number }>("/api/envio/whatsapp/sincronizar"),

  sincronizarLead: (placeId: string) =>
    httpClient.post<{ ok: true; novas: number }>(
      `/api/envio/whatsapp/sincronizar/maps/${encodeURIComponent(placeId)}`
    ),

  caixa: () => httpClient.get<CaixaWhatsapp>("/api/envio/whatsapp/caixa"),

  salvarAvisos: (whatsappNumero: string) =>
    httpClient.post<{ ok: true; whatsapp_numero: string; mesmo_numero_conectado: boolean }>(
      "/api/envio/config/avisos",
      { whatsapp_numero: whatsappNumero }
    ),

  testarTudo: () =>
    httpClient.post<{ ok: boolean; itens: { nome: string; ok: boolean; detalhe: string }[] }>(
      "/api/envio/testar-tudo"
    ),

  testarAviso: () => httpClient.post<{ ok: true; canais: string[] }>("/api/envio/aviso/teste"),

  detectarChatTelegram: () =>
    httpClient.post<{ ok: true; chat_id: string; nome: string }>("/api/envio/telegram/detectar-chat"),

  testarTelegram: () => httpClient.post<{ ok: true }>("/api/envio/telegram/teste"),

  enviarResumoTelegram: () => httpClient.post<{ ok: true }>("/api/envio/telegram/resumo"),
}
