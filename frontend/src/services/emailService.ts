import { httpClient } from "@/services/httpClient"

export type StatusEmail = "novo" | "contatado" | "respondeu" | "recusou" | "descadastrado" | "invalido"
export type FonteEmail = "site" | "receita" | "manual"

export interface ConfigSmtp {
  host: string
  porta: number
  usuario: string
  senha_configurada: boolean
  senha_mascarada: string | null
  remetente_nome: string
  remetente_email: string
  limite_diario: number
  enviados_hoje: number
  assinatura: string
  anexar_pdf: boolean
  primeiro_simples: boolean
  anexo_pdf: string
  anexo_pdf_existe: boolean
}

export type EstiloEmail = "simples" | "marca" | "marca_pdf"

export const ROTULO_ESTILO_EMAIL: Record<EstiloEmail, string> = {
  simples: "Texto simples (cai mais na caixa de entrada)",
  marca: "Com a marca (logo e assinatura)",
  marca_pdf: "Com a marca e o PDF da proposta",
}

export interface SalvarSmtp {
  host: string
  porta: number
  usuario: string
  senha?: string
  remetente_nome: string
  remetente_email: string
  limite_diario: number
  assinatura: string
  anexar_pdf: boolean
  primeiro_simples: boolean
}

export interface LeadEmail {
  id: number
  empresa: string
  email: string
  setor: string | null
  cidade: string | null
  site_url: string | null
  fonte: FonteEmail
  status: StatusEmail
  follow_ups_enviados: number
  ultimo_envio_em: string | null
  criado_em: string
}

export interface FiltrosEmail {
  status: string
  setor: string
  cidade: string
  busca: string
  pagina: number
  por_pagina: number
}

export interface ListaLeadsEmail {
  leads: LeadEmail[]
  total: number
  setores: string[]
  cidades: string[]
  contagem_por_status: Partial<Record<StatusEmail, number>>
}

export interface EstadoImportacaoSites {
  rodando: boolean
  processados: number
  total: number
  novos: number
  mensagem: string
}

export interface ImportarReceita {
  arquivo: string
  cnaes: string[]
  uf: string
  municipio?: string
  limite?: number
}

export interface NovoLeadEmail {
  empresa: string
  email: string
  setor?: string
  cidade?: string
  site_url?: string
}

export interface MensagemHistorico {
  autor: "vendedor" | "lead"
  texto: string
  enviada_em: string
}

export interface EmailGerado {
  assunto: string
  corpo: string
  provedor: string
}

function montarQuery(filtros: FiltrosEmail): string {
  const params = new URLSearchParams()
  if (filtros.status) params.set("status", filtros.status)
  if (filtros.setor) params.set("setor", filtros.setor)
  if (filtros.cidade) params.set("cidade", filtros.cidade)
  if (filtros.busca.trim()) params.set("busca", filtros.busca.trim())
  params.set("pagina", String(filtros.pagina))
  params.set("por_pagina", String(filtros.por_pagina))
  return params.toString()
}

export const emailService = {
  obterConfig: () => httpClient.get<{ smtp: ConfigSmtp }>("/api/email/config"),

  salvarConfig: (dados: SalvarSmtp) => httpClient.post<{ ok: true }>("/api/email/config", dados),

  testarConfig: (para: string, estilo?: EstiloEmail) =>
    httpClient.post<{ ok: true }>("/api/email/config/testar", { para, estilo }),

  listarLeads: (filtros: FiltrosEmail) =>
    httpClient.get<ListaLeadsEmail>(`/api/email/leads?${montarQuery(filtros)}`),

  importarSites: () => httpClient.post<{ iniciado: true }>("/api/email/importar/sites"),

  estadoImportacaoSites: () => httpClient.get<EstadoImportacaoSites>("/api/email/importar/estado"),

  importarReceita: (dados: ImportarReceita) =>
    httpClient.post<{ importados: number; ignorados: number }>("/api/email/importar/receita", dados),

  adicionarLead: (dados: NovoLeadEmail) => httpClient.post<{ id: number }>("/api/email/leads", dados),

  gerar: (id: number) => httpClient.post<EmailGerado>(`/api/email/leads/${id}/gerar`),

  enviar: (id: number, dados: { assunto: string; corpo: string; estilo?: EstiloEmail }) =>
    httpClient.post<{ ok: true; status: StatusEmail }>(`/api/email/leads/${id}/enviar`, dados),

  mudarStatus: (id: number, status: StatusEmail) =>
    httpClient.post<{ ok: true }>(`/api/email/leads/${id}/status`, { status }),

  historico: (id: number) =>
    httpClient.get<{ mensagens: MensagemHistorico[] }>(`/api/email/leads/${id}/historico`),

  listarDescadastros: () => httpClient.get<{ emails: string[] }>("/api/email/descadastros"),

  adicionarDescadastro: (email: string) =>
    httpClient.post<{ ok: true }>("/api/email/descadastros", { email }),
}
