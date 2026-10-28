import { httpClient } from "@/services/httpClient"

export interface ConfigPiloto {
  piloto_ativo: string
  piloto_auto_resposta: string
  piloto_nicho: string
  piloto_cidade: string
  piloto_score_min: string
  piloto_hora_inicio: string
  piloto_hora_fim: string
  piloto_fim_de_semana: string
  piloto_intervalo_min: string
  piloto_intervalo_max: string
  piloto_max_respostas: string
  piloto_info_oferta: string
}

export interface LeadFila {
  place_id: string
  nome: string
  nicho: string | null
  cidade: string | null
  nota: number | null
  num_avaliacoes: number | null
  site_status: string | null
  score: number
}

export type TipoEventoPiloto =
  | "contato_enviado"
  | "resposta_enviada"
  | "passou_para_voce"
  | "encerrado"
  | "sem_whatsapp"
  | "erro"
  | "ligado"
  | "desligado"
  | "voce_assumiu"
  | "devolvido_ao_piloto"

export interface EventoPiloto {
  id: number
  em: string
  tipo: TipoEventoPiloto
  place_id: string | null
  nome: string | null
  detalhe: string | null
}

export interface PainelPiloto {
  config: ConfigPiloto
  estado: {
    proximo_contato_em: string | null
    ultimo_erro: string | null
    rodando: boolean
    whatsapp: string
    dentro_do_horario: boolean
    enviados_hoje: number
    limite_diario: number
  }
  fila: LeadFila[]
  disponiveis: number
  contagem: { conduzindo: number; com_voce: number; encerrados: number; sem_whatsapp: number }
  precisa_de_voce: {
    place_id: string
    nome: string
    ultimo_texto: string
    ultima_em: string
    motivo: string | null
  }[]
  eventos: EventoPiloto[]
  areas: { nichos: string[]; cidades: string[] }
}

export type SalvarConfigPiloto = Partial<
  Omit<ConfigPiloto, "piloto_auto_resposta" | "piloto_fim_de_semana" | "piloto_ativo">
> & { piloto_auto_resposta?: boolean; piloto_fim_de_semana?: boolean }

export const pilotoService = {
  painel: () => httpClient.get<PainelPiloto>("/api/piloto"),
  salvarConfig: (dados: SalvarConfigPiloto) =>
    httpClient.post<{ ok: true; config: ConfigPiloto }>("/api/piloto/config", dados),
  ativar: (ativo: boolean) => httpClient.post<{ ok: true; ativo: boolean }>("/api/piloto/ativar", { ativo }),
  enviarProximo: () => httpClient.post<{ ok: true; nome: string }>("/api/piloto/enviar-proximo"),
  assumir: (placeId: string) =>
    httpClient.post<{ ok: true }>(`/api/piloto/assumir/${encodeURIComponent(placeId)}`),
  devolver: (placeId: string) =>
    httpClient.post<{ ok: true }>(`/api/piloto/devolver/${encodeURIComponent(placeId)}`),
}
