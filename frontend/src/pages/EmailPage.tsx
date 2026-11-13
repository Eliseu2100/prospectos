import { useEffect, useState } from "react"
import { Ban, Mail, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHero } from "@/components/shared/PageHero"
import { EmptyStateCard } from "@/components/shared/EmptyStateCard"
import { PaginacaoSimples } from "@/components/shared/PaginacaoSimples"
import { HistoricoMensagensDialog } from "@/components/shared/HistoricoMensagensDialog"
import { SearchInput } from "@/components/filters/SearchInput"
import { SelectComVazio } from "@/components/filters/SelectComVazio"
import { ConfigSmtpCard } from "@/components/email/ConfigSmtpCard"
import { BarraAcoesEmail } from "@/components/email/BarraAcoesEmail"
import { TabelaLeadsEmail } from "@/components/email/TabelaLeadsEmail"
import { EscreverEmailDialog } from "@/components/email/EscreverEmailDialog"
import { ImportarReceitaDialog } from "@/components/email/ImportarReceitaDialog"
import { AdicionarEmailDialog } from "@/components/email/AdicionarEmailDialog"
import { DescadastrosDialog } from "@/components/email/DescadastrosDialog"
import { useHistoricoEmail, useLeadsEmail, useMudarStatusEmail } from "@/hooks/useEmail"
import { ORDEM_STATUS_EMAIL, STATUS_EMAIL } from "@/lib/statusCanais"
import { cn } from "@/lib/utils"
import type { LeadEmail } from "@/services/emailService"

const POR_PAGINA = 50

/** Prospecção por e-mail: configura o SMTP, junta e-mails (sites dos leads, base
 * da Receita ou à mão) e escreve/envia um por vez, sempre com revisão humana. */
export function EmailPage() {
  const [status, setStatus] = useState("")
  const [setor, setSetor] = useState("")
  const [cidade, setCidade] = useState("")
  const [busca, setBusca] = useState("")
  const [buscaAplicada, setBuscaAplicada] = useState("")
  const [pagina, setPagina] = useState(1)

  const [leadEscrever, setLeadEscrever] = useState<LeadEmail | null>(null)
  const [leadHistorico, setLeadHistorico] = useState<LeadEmail | null>(null)
  const [receitaAberta, setReceitaAberta] = useState(false)
  const [adicionarAberto, setAdicionarAberto] = useState(false)
  const [descadastrosAberto, setDescadastrosAberto] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => {
      setBuscaAplicada(busca)
      setPagina(1)
    }, 350)
    return () => clearTimeout(t)
  }, [busca])

  const { data, isLoading } = useLeadsEmail({
    status,
    setor,
    cidade,
    busca: buscaAplicada,
    pagina,
    por_pagina: POR_PAGINA,
  })
  const mudarStatus = useMudarStatusEmail()
  const historico = useHistoricoEmail(leadHistorico?.id ?? null)

  const contagem = data?.contagem_por_status ?? {}
  const totalGeral = ORDEM_STATUS_EMAIL.reduce((soma, s) => soma + (contagem[s] ?? 0), 0)
  const leads = data?.leads ?? []
  const filtrando = Boolean(status || setor || cidade || buscaAplicada)

  function filtrar(aplicar: () => void) {
    aplicar()
    setPagina(1)
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6 sm:px-6">
      <PageHero
        icone={<Mail className="size-6" />}
        titulo="Prospecção por e-mail"
        descricao="Junte e-mails de empresas, revise o texto e envie um de cada vez."
        gradiente="from-primary/90 to-primary/70"
        acoes={
          <Button size="sm" variant="secondary" onClick={() => setDescadastrosAberto(true)}>
            <Ban className="size-4" />
            Lista de descadastros
          </Button>
        }
      />

      <div className="flex items-start gap-3 rounded-2xl bg-card px-4 py-3 text-sm text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
        <p>
          Todo e-mail sai com identificação e pedido de descadastro. Quem pedir para sair vai para a lista de
          descadastros e não recebe mais nada.
        </p>
      </div>

      <ConfigSmtpCard />

      <BarraAcoesEmail
        onImportarReceita={() => setReceitaAberta(true)}
        onAdicionar={() => setAdicionarAberto(true)}
      />

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
        {ORDEM_STATUS_EMAIL.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => filtrar(() => setStatus(s))}
            className={cn(
              "rounded-full px-3 py-1 text-sm font-medium transition-colors",
              status === s ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted"
            )}
          >
            {STATUS_EMAIL[s].rotulo} <span className="tabular-nums opacity-70">({contagem[s] ?? 0})</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <SearchInput valor={busca} onChange={setBusca} placeholder="Buscar por empresa ou e-mail..." />
        <SelectComVazio
          valor={setor}
          onChange={(v) => filtrar(() => setSetor(v))}
          opcoes={(data?.setores ?? []).map((s) => ({ valor: s, label: s }))}
          labelVazio="Todos os setores"
          placeholder="Setor"
          className="w-48"
        />
        <SelectComVazio
          valor={cidade}
          onChange={(v) => filtrar(() => setCidade(v))}
          opcoes={(data?.cidades ?? []).map((c) => ({ valor: c, label: c }))}
          labelVazio="Todas as cidades"
          placeholder="Cidade"
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
          icone={<Mail className="size-5" />}
          titulo={filtrando ? "Nenhum e-mail com esses filtros" : "Nenhum e-mail ainda"}
          descricao={
            filtrando
              ? "Tire um filtro ou mude a busca."
              : "Busque nos sites dos seus leads, importe da base da Receita ou adicione um e-mail à mão."
          }
        />
      ) : (
        <>
          <TabelaLeadsEmail
            leads={leads}
            onEscrever={setLeadEscrever}
            onHistorico={setLeadHistorico}
            onMudarStatus={(lead, novo) => mudarStatus.mutate({ id: lead.id, status: novo })}
          />
          <PaginacaoSimples pagina={pagina} porPagina={POR_PAGINA} total={data?.total ?? 0} onChange={setPagina} />
        </>
      )}

      <EscreverEmailDialog lead={leadEscrever} onFechar={() => setLeadEscrever(null)} />
      <HistoricoMensagensDialog
        aberto={leadHistorico !== null}
        onFechar={() => setLeadHistorico(null)}
        titulo={leadHistorico ? `${leadHistorico.empresa} · ${leadHistorico.email}` : ""}
        mensagens={historico.data?.mensagens}
        carregando={historico.isLoading}
      />
      <ImportarReceitaDialog aberto={receitaAberta} onFechar={() => setReceitaAberta(false)} />
      <AdicionarEmailDialog aberto={adicionarAberto} onFechar={() => setAdicionarAberto(false)} />
      <DescadastrosDialog aberto={descadastrosAberto} onFechar={() => setDescadastrosAberto(false)} />
    </div>
  )
}
