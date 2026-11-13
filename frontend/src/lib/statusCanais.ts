import type { TomPilula } from "@/components/shared/PilulaStatus"
import type { FonteEmail, StatusEmail } from "@/services/emailService"
import type { StatusLinkedin } from "@/services/linkedinService"

interface InfoStatus {
  rotulo: string
  tom: TomPilula
}

export const STATUS_EMAIL: Record<StatusEmail, InfoStatus> = {
  novo: { rotulo: "Novo", tom: "azul" },
  contatado: { rotulo: "Contatado", tom: "ambar" },
  respondeu: { rotulo: "Respondeu", tom: "verde" },
  recusou: { rotulo: "Recusou", tom: "vermelho" },
  descadastrado: { rotulo: "Descadastrado", tom: "vermelho" },
  invalido: { rotulo: "Inválido", tom: "neutro" },
}

export const ORDEM_STATUS_EMAIL = Object.keys(STATUS_EMAIL) as StatusEmail[]

export const ROTULO_FONTE_EMAIL: Record<FonteEmail, string> = {
  site: "Site do lead",
  receita: "Receita",
  manual: "Manual",
}

export const STATUS_LINKEDIN: Record<StatusLinkedin, InfoStatus> = {
  novo: { rotulo: "Novo", tom: "azul" },
  conexao_enviada: { rotulo: "Conexão enviada", tom: "ambar" },
  conectado: { rotulo: "Conectado", tom: "ambar" },
  mensagem_enviada: { rotulo: "Mensagem enviada", tom: "ambar" },
  respondeu: { rotulo: "Respondeu", tom: "verde" },
  recusou: { rotulo: "Recusou", tom: "vermelho" },
  ignorado: { rotulo: "Ignorado", tom: "neutro" },
}

export const ORDEM_STATUS_LINKEDIN = Object.keys(STATUS_LINKEDIN) as StatusLinkedin[]
