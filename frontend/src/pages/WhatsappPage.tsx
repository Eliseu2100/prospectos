import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { MessagesSquare, RefreshCw, Settings } from "lucide-react"
import { Header } from "@/components/layout/Header"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHero } from "@/components/shared/PageHero"
import { EmptyStateCard } from "@/components/shared/EmptyStateCard"
import { StatusBadge } from "@/components/leads/StatusBadge"
import { useCaixaWhatsapp, useSincronizarTodos, useWhatsappConectado } from "@/hooks/useEnvio"
import { formatarTempoRelativo } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import type { ConversaCaixa } from "@/services/envioService"
import type { StatusLead } from "@/types/lead"

type Aba = "aguardando" | "sem_resposta" | "todas"

const ABAS: { valor: Aba; rotulo: string; filtro: (c: ConversaCaixa) => boolean }[] = [
  { valor: "aguardando", rotulo: "Responderam (sua vez)", filtro: (c) => c.aguardando_voce },
  { valor: "sem_resposta", rotulo: "Ainda não responderam", filtro: (c) => !c.ja_respondeu },
  { valor: "todas", rotulo: "Todas", filtro: () => true },
]

/** Caixa de entrada do WhatsApp: as conversas com os leads, dentro do app.
 * As mensagens vêm da Evolution API (sincronização em segundo plano no backend). */
export function WhatsappPage() {
  const conectado = useWhatsappConectado()
  const { data, isLoading } = useCaixaWhatsapp()
  const sincronizar = useSincronizarTodos()
  const [aba, setAba] = useState<Aba>("aguardando")

  const conversas = useMemo(() => data?.conversas ?? [], [data])
  const contagem = useMemo(
    () => Object.fromEntries(ABAS.map((a) => [a.valor, conversas.filter(a.filtro).length])) as Record<Aba, number>,
    [conversas]
  )
  const filtradas = conversas.filter(ABAS.find((a) => a.valor === aba)!.filtro)

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="mx-auto w-full max-w-4xl space-y-4 px-4 py-6 sm:px-6">
        <PageHero
          icone={<MessagesSquare className="size-6" />}
          titulo="WhatsApp"
          descricao="Suas conversas com os leads, sem sair do Seriax OS."
          gradiente="from-success/85 via-success/75 to-primary/80"
          acoes={
            conectado && (
              <Button
                size="sm"
                variant="secondary"
                disabled={sincronizar.isPending}
                onClick={() => sincronizar.mutate()}
              >
                <RefreshCw className={cn("size-4", sincronizar.isPending && "animate-spin")} />
                {sincronizar.isPending ? "Buscando..." : "Atualizar agora"}
              </Button>
            )
          }
        />

        {!conectado && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm">
            <p>
              O WhatsApp não está conectado na ferramenta. Conecte pelo QR code em
              Configurações para as respostas dos clientes aparecerem aqui.
            </p>
            <Button size="sm" variant="outline" asChild>
              <Link to="/configuracoes">
                <Settings className="size-4" />
                Configurações
              </Link>
            </Button>
          </div>
        )}

        <div className="flex flex-wrap gap-1.5">
          {ABAS.map((a) => (
            <button
              key={a.valor}
              type="button"
              onClick={() => setAba(a.valor)}
              className={cn(
                "rounded-full px-3 py-1 text-sm font-medium transition-colors",
                aba === a.valor ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted"
              )}
            >
              {a.rotulo} <span className="tabular-nums opacity-70">({contagem[a.valor] ?? 0})</span>
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[72px]" />
            ))}
          </div>
        ) : filtradas.length === 0 ? (
          <EmptyStateCard
            icone={<MessagesSquare className="size-5" />}
            titulo={aba === "aguardando" ? "Ninguém esperando resposta" : "Nenhuma conversa aqui"}
            descricao={
              aba === "aguardando"
                ? "Quando um lead responder no WhatsApp, ele aparece aqui."
                : "Envie a primeira mensagem a partir de um lead para a conversa aparecer."
            }
          />
        ) : (
          <ul className="space-y-2">
            {filtradas.map((c) => (
              <li key={c.place_id}>
                <Link
                  to={`/conversas/${encodeURIComponent(c.place_id)}`}
                  className={cn(
                    "flex items-center gap-3 rounded-xl border bg-card p-3 transition-colors hover:bg-accent/50",
                    c.aguardando_voce ? "border-success/50" : "border-border"
                  )}
                >
                  <span
                    className={cn(
                      "size-2.5 shrink-0 rounded-full",
                      c.aguardando_voce ? "bg-success" : "bg-transparent"
                    )}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-medium">{c.nome}</p>
                      <StatusBadge status={c.status as StatusLead} />
                    </div>
                    <p className="truncate text-sm text-muted-foreground">
                      {c.ultimo_autor === "vendedor" && "Você: "}
                      {c.ultimo_texto}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatarTempoRelativo(c.ultima_em)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
