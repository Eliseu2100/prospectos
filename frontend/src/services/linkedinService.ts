import { httpClient } from "@/services/httpClient"
import type { MensagemHistorico } from "@/services/emailService"

export type StatusLinkedin =
  | "novo"
  | "conexao_enviada"
  | "conectado"
  | "mensagem_enviada"
  | "respondeu"
  | "recusou"
  | "ignorado"

export type TipoTextoLinkedin = "conexao" | "mensagem" | "followup"

export interface LeadLinkedin {
  id: number
  nome: string
  cargo: string | null
  empresa: string | null
  perfil_url: string | null
  setor: string | null
  cidade: string | null
  status: StatusLinkedin
  ultimo_texto: string | null
  follow_ups_enviados: number
  proximo_followup: string | null
  criado_em: string
}

export interface FiltrosLinkedin {
  status: string
  setor: string
  busca: string
  pagina: number
  por_pagina: number
}

export interface ListaLeadsLinkedin {
  leads: LeadLinkedin[]
  total: number
  setores: string[]
  contagem_por_status: Partial<Record<StatusLinkedin, number>>
}

export interface NovoLeadLinkedin {
  nome: string
  cargo?: string
  empresa?: string
  perfil_url?: string
  setor?: string
  cidade?: string
}

export interface TextoLinkedinGerado {
  texto: string
  provedor: string
  limite_caracteres: number
}

function montarQuery(filtros: FiltrosLinkedin): string {
  const params = new URLSearchParams()
  if (filtros.status) params.set("status", filtros.status)
  if (filtros.setor) params.set("setor", filtros.setor)
  if (filtros.busca.trim()) params.set("busca", filtros.busca.trim())
  params.set("pagina", String(filtros.pagina))
  params.set("por_pagina", String(filtros.por_pagina))
  return params.toString()
}

export const linkedinService = {
  importarCsv: (csv: string) =>
    httpClient.post<{ importados: number; ignorados: number }>("/api/linkedin/importar", { csv }),

  adicionarLead: (dados: NovoLeadLinkedin) =>
    httpClient.post<{ id: number }>("/api/linkedin/leads", dados),

  listarLeads: (filtros: FiltrosLinkedin) =>
    httpClient.get<ListaLeadsLinkedin>(`/api/linkedin/leads?${montarQuery(filtros)}`),

  gerar: (id: number, tipo: TipoTextoLinkedin) =>
    httpClient.post<TextoLinkedinGerado>(`/api/linkedin/leads/${id}/gerar`, { tipo }),

  mudarStatus: (id: number, status: StatusLinkedin, texto?: string) =>
    httpClient.post<{ ok: true }>(`/api/linkedin/leads/${id}/status`, { status, texto }),

  historico: (id: number) =>
    httpClient.get<{ mensagens: MensagemHistorico[] }>(`/api/linkedin/leads/${id}/historico`),
}
