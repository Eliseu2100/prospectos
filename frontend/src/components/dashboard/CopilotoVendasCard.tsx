import { useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight, Bot, CheckCircle2, Send, Sparkles } from "lucide-react"
import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { httpClient } from "@/services/httpClient"

interface LeadDestaque {
  place_id: string
  nome: string
  motivo: string
}

interface RespostaCopiloto {
  resposta: string
  acoes_recomendadas: string[]
  leads_destaque: LeadDestaque[]
  provedor?: string | null
  avisos?: string[]
}

const ATALHOS_RAPIDOS = [
  "Quais leads que responderam estão mais perto de fechar hoje?",
  "Quais leads novos têm o maior potencial para abordar agora?",
  "Qual cidade e nicho estão convertendo melhor no meu funil?",
  "O que devo priorizar agora para fechar vendas esta semana?",
]

export function CopilotoVendasCard() {
  const [pergunta, setPergunta] = useState("")

  const consultar = useMutation({
    mutationFn: (texto: string) =>
      httpClient.post<RespostaCopiloto>("/api/analytics/copiloto", { pergunta: texto }),
    onError: (erro: Error) => toast.error(erro.message),
  })

  const enviar = (texto: string) => {
    const limpa = texto.trim()
    if (!limpa || consultar.isPending) return
    setPergunta(limpa)
    consultar.mutate(limpa)
  }

  const dados = consultar.data

  return (
    <section className="rounded-[28px] bg-card p-6 sm:p-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Bot className="size-5" />
          </div>
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
              Copiloto Comercial IA
              <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary">
                Consultas inteligentes
              </span>
            </h2>
            <p className="text-sm text-muted-foreground">
              Pergunte sobre seu funil, negociações em andamento no WhatsApp e onde focar hoje.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {ATALHOS_RAPIDOS.map((atalho) => (
          <button
            key={atalho}
            type="button"
            disabled={consultar.isPending}
            onClick={() => enviar(atalho)}
            className="inline-flex items-center gap-1.5 rounded-full bg-muted/60 px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/10 hover:text-primary disabled:opacity-50"
          >
            <Sparkles className="size-3 text-primary" />
            {atalho}
          </button>
        ))}
      </div>

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          enviar(pergunta)
        }}
      >
        <Input
          value={pergunta}
          onChange={(e) => setPergunta(e.target.value)}
          placeholder="Ex.: Quem respondeu no WhatsApp e precisa da minha atenção agora?"
          className="rounded-full"
        />
        <Button
          type="submit"
          disabled={!pergunta.trim() || consultar.isPending}
          className="shrink-0 rounded-full px-5"
        >
          <Send className="size-4" />
          {consultar.isPending ? "Analisando..." : "Perguntar"}
        </Button>
      </form>

      {dados && (
        <div className="mt-5 space-y-4 rounded-2xl bg-muted/40 p-4 sm:p-5">
          <p className="text-sm leading-relaxed text-foreground">{dados.resposta}</p>

          {dados.acoes_recomendadas.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Próximas ações recomendadas
              </h3>
              <ul className="mt-2 space-y-1.5">
                {dados.acoes_recomendadas.map((acao) => (
                  <li key={acao} className="flex items-start gap-2 text-sm text-foreground">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                    <span>{acao}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {dados.leads_destaque.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Leads em destaque para agir agora
              </h3>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {dados.leads_destaque.map((lead) => (
                  <Link
                    key={lead.place_id}
                    to={`/conversas/${encodeURIComponent(lead.place_id)}`}
                    className="group flex items-center justify-between gap-3 rounded-xl bg-card p-3 transition-colors hover:bg-accent/50"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{lead.nome}</p>
                      {lead.motivo && (
                        <p className="truncate text-xs text-muted-foreground">{lead.motivo}</p>
                      )}
                    </div>
                    <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
