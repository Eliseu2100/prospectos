import { useEffect, useState } from "react"
import { Plus, ShieldAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHero } from "@/components/shared/PageHero"
import { EmptyStateCard } from "@/components/shared/EmptyStateCard"
import { PaginacaoSimples } from "@/components/shared/PaginacaoSimples"
import { HistoricoMensagensDialog } from "@/components/shared/HistoricoMensagensDialog"
import { SearchInput } from "@/components/filters/SearchInput"
import { SelectComVazio } from "@/components/filters/SelectComVazio"
import { LinkedinIcon } from "@/components/icons/LinkedinIcon"
import { ImportarCsvCard } from "@/components/linkedin/ImportarCsvCard"
import { TabelaLeadsLinkedin } from "@/components/linkedin/TabelaLeadsLinkedin"
import { TextoLinkedinDialog, type PedidoTextoLinkedin } from "@/components/linkedin/TextoLinkedinDialog"
import { AdicionarLinkedinDialog } from "@/components/linkedin/AdicionarLinkedinDialog"
import { useHistoricoLinkedin, useLeadsLinkedin, useMudarStatusLinkedin } from "@/hooks/useLinkedin"
import { ORDEM_STATUS_LINKEDIN, STATUS_LINKEDIN } from "@/lib/statusCanais"
import { cn } from "@/lib/utils"
import type { LeadLinkedin } from "@/services/linkedinService"

const POR_PAGINA = 50

/** Prospecção assistida no LinkedIn: o app importa os contatos e escreve os
 * textos, mas o envio é sempre manual, para não arriscar a conta. */
export function LinkedinPage() {
  const [status, setStatus] = useState("")
  const [setor, setSetor] = useState("")
  const [busca, setBusca] = useState("")
  const [buscaAplicada, setBuscaAplicada] = useState("")
  const [pagina, setPagina] = useState(1)

  const [pedidoTexto, setPedidoTexto] = useState<PedidoTextoLinkedin | null>(null)
  const [leadHistorico, setLeadHistorico] = useState<LeadLinkedin | null>(null)
  const [adicionarAberto, setAdicionarAberto] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => {
      setBuscaAplicada(busca)
      setPagina(1)
    }, 350)
    return () => clearTimeout(t)
  }, [busca])

  const { data, isLoading } = useLeadsLinkedin({
    status,
    setor,
    busca: buscaAplicada,
    pagina,
    por_pagina: POR_PAGINA,
  })
  const mudarStatus = useMudarStatusLinkedin()
  const historico = useHistoricoLinkedin(leadHistorico?.id ?? null)

  const contagem = data?.contagem_por_status ?? {}
  const totalGeral = ORDEM_STATUS_LINKEDIN.reduce((soma, s) => soma + (contagem[s] ?? 0), 0)
  const leads = data?.leads ?? []
  const filtrando = Boolean(status || setor || buscaAplicada)

  function filtrar(aplicar: () => void) {
    aplicar()
    setPagina(1)
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6 sm:px-6">
      <PageHero
        icone={<LinkedinIcon className="size-6" />}
        titulo="LinkedIn"
        descricao="Textos prontos para conexão, mensagem e follow-up. O envio é seu."
        gradiente="from-primary/90 to-primary/70"
        acoes={
          <Button size="sm" variant="secondary" onClick={() => setAdicionarAberto(true)}>
            <Plus className="size-4" />
            Adicionar contato
          </Button>
        }
      />

      <div className="flex items-start gap-3 rounded-2xl bg-card px-4 py-3 text-sm text-muted-foreground">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning-foreground" />
        <p>
          O app não envia nada ao LinkedIn, para proteger a sua conta. Você copia o texto, envia por lá e volta
          aqui para marcar o passo como feito.
        </p>
      </div>

      <ImportarCsvCard />

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => filtrar(() => setStatus(""))}
          className={cn(
            "rounded-full px-3 py-1 text-sm font-medium transition-colors",
            status === "" ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted"
          )}
        >
          Todos <span className="tabular-nums opacity-70">({totalGeral})</span>
        </button>
        {ORDEM_STATUS_LINKEDIN.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => filtrar(() => setStatus(s))}
            className={cn(
              "rounded-full px-3 py-1 text-sm font-medium transition-colors",
              status === s ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted"
            )}
          >
            {STATUS_LINKEDIN[s].rotulo} <span className="tabular-nums opacity-70">({contagem[s] ?? 0})</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <SearchInput valor={busca} onChange={setBusca} placeholder="Buscar por nome, cargo ou empresa..." />
        <SelectComVazio
          valor={setor}
          onChange={(v) => filtrar(() => setSetor(v))}
          opcoes={(data?.setores ?? []).map((s) => ({ valor: s, label: s }))}
          labelVazio="Todos os setores"
          placeholder="Setor"
          className="w-48"
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 rounded-2xl" />
          ))}
        </div>
      ) : leads.length === 0 ? (
        <EmptyStateCard
          icone={<LinkedinIcon className="size-5" />}
          titulo={filtrando ? "Nenhum contato com esses filtros" : "Nenhum contato ainda"}
          descricao={
            filtrando
              ? "Tire um filtro ou mude a busca."
              : "Importe um CSV do LinkedIn ou do Sales Navigator, ou adicione um contato à mão."
          }
        />
      ) : (
        <>
          <TabelaLeadsLinkedin
            leads={leads}
            onGerar={(lead, tipo) => setPedidoTexto({ lead, tipo })}
            onHistorico={setLeadHistorico}
            onMudarStatus={(lead, novo) => mudarStatus.mutate({ id: lead.id, status: novo })}
          />
          <PaginacaoSimples pagina={pagina} porPagina={POR_PAGINA} total={data?.total ?? 0} onChange={setPagina} />
        </>
      )}

      <TextoLinkedinDialog pedido={pedidoTexto} onFechar={() => setPedidoTexto(null)} />
      <HistoricoMensagensDialog
        aberto={leadHistorico !== null}
        onFechar={() => setLeadHistorico(null)}
        titulo={leadHistorico ? `${leadHistorico.nome}${leadHistorico.empresa ? ` · ${leadHistorico.empresa}` : ""}` : ""}
        mensagens={historico.data?.mensagens}
        carregando={historico.isLoading}
      />
      <AdicionarLinkedinDialog aberto={adicionarAberto} onFechar={() => setAdicionarAberto(false)} />
    </div>
  )
}
