import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertTriangle,
  Ban,
  Bot,
  CheckCircle2,
  Clock,
  Hand,
  Palette,
  MessageCircle,
  Pause,
  Play,
  Power,
  Reply,
  Search,
  Send,
  Undo2,
} from "lucide-react"
import { Header } from "@/components/layout/Header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { useBusca } from "@/hooks/useBusca"
import {
  useAtivarPiloto,
  useDevolverAoPiloto,
  useEnviarProximo,
  usePainelPiloto,
  useSalvarConfigPiloto,
} from "@/hooks/usePiloto"
import { formatarTempoRelativo } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import type { ConfigPiloto, EventoPiloto, PainelPiloto } from "@/services/pilotoService"

const ICONE_EVENTO: Record<EventoPiloto["tipo"], { icone: React.ReactNode; rotulo: string; cor: string }> = {
  contato_enviado: { icone: <Send className="size-3.5" />, rotulo: "Primeiro contato enviado", cor: "text-primary" },
  resposta_enviada: { icone: <Reply className="size-3.5" />, rotulo: "Respondeu automaticamente", cor: "text-primary" },
  previa_combinada: { icone: <Palette className="size-3.5" />, rotulo: "Prévia combinada", cor: "text-success" },
  passou_para_voce: { icone: <Hand className="size-3.5" />, rotulo: "Passou a conversa para você", cor: "text-warning" },
  encerrado: { icone: <Ban className="size-3.5" />, rotulo: "Lead pediu para parar", cor: "text-muted-foreground" },
  sem_whatsapp: { icone: <Ban className="size-3.5" />, rotulo: "Número sem WhatsApp", cor: "text-muted-foreground" },
  erro: { icone: <AlertTriangle className="size-3.5" />, rotulo: "Erro", cor: "text-destructive" },
  ligado: { icone: <Play className="size-3.5" />, rotulo: "Piloto ligado", cor: "text-success" },
  desligado: { icone: <Pause className="size-3.5" />, rotulo: "Piloto pausado", cor: "text-muted-foreground" },
  voce_assumiu: { icone: <Hand className="size-3.5" />, rotulo: "Você assumiu a conversa", cor: "text-muted-foreground" },
  devolvido_ao_piloto: { icone: <Bot className="size-3.5" />, rotulo: "Conversa devolvida ao piloto", cor: "text-muted-foreground" },
}

function Secao({ numero, titulo, descricao, children }: {
  numero?: number
  titulo: string
  descricao?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-[28px] bg-card p-6 sm:p-8">
      <div className="mb-5">
        <h3 className="flex items-center gap-2.5 text-xl font-semibold tracking-tight">
          {numero && (
            <span className="flex size-7 items-center justify-center rounded-full bg-foreground text-sm text-background">
              {numero}
            </span>
          )}
          {titulo}
        </h3>
        {descricao && <p className="mt-1 text-[15px] text-muted-foreground">{descricao}</p>}
      </div>
      {children}
    </section>
  )
}

function Indicador({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
        ok ? "bg-success/12 text-success" : "bg-warning/12 text-warning"
      )}
    >
      <span className={cn("size-1.5 rounded-full", ok ? "bg-success" : "bg-warning")} />
      {children}
    </span>
  )
}

function Numero({ valor, rotulo }: { valor: React.ReactNode; rotulo: string }) {
  return (
    <div>
      <p className="text-3xl font-semibold tracking-tight tabular-nums">{valor}</p>
      <p className="text-[13px] text-muted-foreground">{rotulo}</p>
    </div>
  )
}

function Painel({ dados }: { dados: PainelPiloto }) {
  const ativar = useAtivarPiloto()
  const enviarProximo = useEnviarProximo()
  const ativo = dados.config.piloto_ativo === "1"
  const { estado } = dados
  const whatsappOk = estado.whatsapp === "open"

  let situacao = "Pausado. Ligue para começar a prospectar sozinho."
  if (ativo && !whatsappOk) situacao = "Ligado, mas esperando o WhatsApp ser conectado."
  else if (ativo && !estado.dentro_do_horario) situacao = "Ligado, aguardando o horário de envio."
  else if (ativo && estado.enviados_hoje >= estado.limite_diario) situacao = "Ligado. Limite de hoje atingido, continua amanhã."
  else if (ativo && dados.disponiveis === 0) situacao = "Ligado, mas não há leads novos nessa área. Busque mais abaixo."
  else if (ativo) situacao = estado.proximo_contato_em
    ? `Ligado. Próximo contato ${formatarTempoRelativo(estado.proximo_contato_em)}.`
    : "Ligado. O primeiro contato sai em instantes."

  return (
    <div className="rounded-[28px] bg-card p-6 sm:p-8">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "flex size-14 shrink-0 items-center justify-center rounded-2xl transition-colors",
              ativo ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
            )}
          >
            <Bot className="size-7" />
          </div>
          <div>
            <h2 className="text-[28px] leading-tight font-semibold tracking-tight">Piloto automático</h2>
            <p className="mt-1 max-w-xl text-[15px] text-muted-foreground">{situacao}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Indicador ok={whatsappOk}>{whatsappOk ? "WhatsApp conectado" : "WhatsApp desconectado"}</Indicador>
              <Indicador ok={estado.dentro_do_horario}>
                {estado.dentro_do_horario ? "Dentro do horário" : "Fora do horário"}
              </Indicador>
            </div>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button
            size="lg"
            variant={ativo ? "secondary" : "default"}
            disabled={ativar.isPending || (!ativo && !whatsappOk)}
            onClick={() => ativar.mutate(!ativo)}
          >
            <Power className="size-4" />
            {ativo ? "Pausar piloto" : "Ligar piloto"}
          </Button>
        </div>
      </div>

      {!whatsappOk && (
        <p className="mt-5 rounded-2xl bg-warning/10 px-4 py-3 text-sm">
          Conecte o WhatsApp em{" "}
          <Link to="/configuracoes" className="font-medium text-link hover:underline">
            Configurações
          </Link>{" "}
          para o piloto poder enviar.
        </p>
      )}
      {estado.ultimo_erro && (
        <p className="mt-5 rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Último erro: {estado.ultimo_erro}
        </p>
      )}

      <div className="mt-7 grid grid-cols-2 gap-6 border-t border-border pt-6 sm:grid-cols-4">
        <Numero valor={`${estado.enviados_hoje}/${estado.limite_diario}`} rotulo="envios hoje" />
        <Numero valor={dados.disponiveis} rotulo="leads na fila" />
        <Numero valor={dados.contagem.conduzindo} rotulo="conversas com o piloto" />
        <Numero valor={dados.contagem.com_voce} rotulo="conversas com você" />
      </div>

      {dados.fila.length > 0 && (
        <div className="mt-6 border-t border-border pt-6">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-sm font-medium">Próximos da fila (melhor score primeiro)</p>
            <Button
              size="sm"
              variant="outline"
              disabled={enviarProximo.isPending || !whatsappOk}
              onClick={() => enviarProximo.mutate(undefined)}
            >
              <Send className="size-3.5" />
              {enviarProximo.isPending ? "Enviando..." : "Enviar o próximo agora"}
            </Button>
          </div>
          <ul className="divide-y divide-border">
            {dados.fila.map((lead) => (
              <li key={lead.place_id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-[15px] font-medium">{lead.nome}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {[lead.nicho, lead.cidade].filter(Boolean).join(" · ")}
                    {lead.nota ? ` · ★ ${lead.nota} (${lead.num_avaliacoes ?? 0})` : ""}
                    {lead.site_status === "sem_site" ? " · sem site" : lead.site_status === "site_ruim" ? " · site ruim" : ""}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-semibold tabular-nums">
                  {lead.score}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function PrecisaDeVoce({ dados }: { dados: PainelPiloto }) {
  const devolver = useDevolverAoPiloto()
  if (!dados.precisa_de_voce.length) return null
  return (
    <section className="rounded-[28px] bg-card p-6 ring-2 ring-warning/40 sm:p-8">
      <h3 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Hand className="size-5 text-warning" />
        Precisam de você ({dados.precisa_de_voce.length})
      </h3>
      <p className="mt-1 text-[15px] text-muted-foreground">
        O piloto parou nessas conversas e deixou com você: preço, fechamento ou algo que ele não deve decidir sozinho.
      </p>
      <ul className="mt-4 space-y-2">
        {dados.precisa_de_voce.map((c) => (
          <li key={c.place_id} className="flex flex-col gap-3 rounded-2xl bg-muted/60 p-4 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{c.nome}</p>
              <p className="truncate text-sm">“{c.ultimo_texto}”</p>
              {c.motivo && <p className="mt-0.5 text-xs text-muted-foreground">Motivo: {c.motivo}</p>}
            </div>
            <div className="flex shrink-0 gap-2">
              <Button size="sm" asChild>
                <Link to={`/conversas/${encodeURIComponent(c.place_id)}`}>
                  <MessageCircle className="size-3.5" />
                  Responder
                </Link>
              </Button>
              <Button size="sm" variant="ghost" onClick={() => devolver.mutate(c.place_id)}>
                <Undo2 className="size-3.5" />
                Devolver ao piloto
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function formatarEntrega(data: string | null) {
  if (!data) return "sem data"
  const alvo = new Date(`${data.slice(0, 10)}T00:00:00`)
  const hoje = new Date()
  hoje.setHours(0, 0, 0, 0)
  const dias = Math.round((alvo.getTime() - hoje.getTime()) / 86_400_000)
  if (dias < 0) return `atrasada (${alvo.toLocaleDateString("pt-BR")})`
  if (dias === 0) return "entregar hoje"
  if (dias === 1) return "entregar amanhã"
  return `entregar ${alvo.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit" })}`
}

function Previas({ dados }: { dados: PainelPiloto }) {
  if (!dados.previas.length) return null
  return (
    <section className="rounded-[28px] bg-card p-6 ring-2 ring-success/35 sm:p-8">
      <h3 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Palette className="size-5 text-success" />
        Prévias para fazer ({dados.previas.length})
      </h3>
      <p className="mt-1 text-[15px] text-muted-foreground">
        Clientes que quiseram ver como ficaria o site. O piloto combinou a entrega para o próximo dia útil:
        monte a prévia e envie pela conversa.
      </p>
      <ul className="mt-4 space-y-2">
        {dados.previas.map((p) => {
          const atrasada = formatarEntrega(p.entregar_em).startsWith("atrasada")
          return (
            <li key={p.place_id} className="flex flex-col gap-3 rounded-2xl bg-muted/60 p-4 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{p.nome}</p>
                <p className={cn("text-sm", atrasada ? "font-medium text-destructive" : "text-muted-foreground")}>
                  {formatarEntrega(p.entregar_em)}
                </p>
              </div>
              <Button size="sm" asChild>
                <Link to={`/conversas/${encodeURIComponent(p.place_id)}`}>
                  <MessageCircle className="size-3.5" />
                  Abrir conversa
                </Link>
              </Button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function Formulario({ dados }: { dados: PainelPiloto }) {
  const salvar = useSalvarConfigPiloto()
  const { dispararBusca, statusBusca } = useBusca()
  const [cfg, setCfg] = useState<ConfigPiloto>(dados.config)

  // recarrega o formulário quando o servidor muda a config (ex.: outra aba)
  useEffect(() => setCfg(dados.config), [dados.config])

  const campo = (chave: keyof ConfigPiloto) => ({
    value: cfg[chave],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setCfg((atual) => ({ ...atual, [chave]: e.target.value })),
  })

  const handleSalvar = () =>
    salvar.mutate({
      piloto_nicho: cfg.piloto_nicho,
      piloto_cidade: cfg.piloto_cidade,
      piloto_score_min: cfg.piloto_score_min,
      piloto_hora_inicio: cfg.piloto_hora_inicio,
      piloto_hora_fim: cfg.piloto_hora_fim,
      piloto_intervalo_min: cfg.piloto_intervalo_min,
      piloto_intervalo_max: cfg.piloto_intervalo_max,
      piloto_max_respostas: cfg.piloto_max_respostas,
      piloto_info_oferta: cfg.piloto_info_oferta,
      piloto_auto_resposta: cfg.piloto_auto_resposta === "1",
      piloto_fim_de_semana: cfg.piloto_fim_de_semana === "1",
    })

  const area = [cfg.piloto_nicho.trim(), cfg.piloto_cidade.trim()].filter(Boolean)
  const buscando = Boolean(statusBusca.data?.rodando) || dispararBusca.isPending
  const mudou = JSON.stringify(cfg) !== JSON.stringify(dados.config)

  return (
    <>
      <Secao
        numero={1}
        titulo="Área"
        descricao="Que tipo de negócio e em qual cidade. O piloto escolhe sozinho os leads com melhor score dessa área."
      >
        <div className="grid gap-4 sm:grid-cols-[1fr_1fr_140px]">
          <div className="space-y-1.5">
            <Label htmlFor="piloto-nicho">Nicho</Label>
            <Input id="piloto-nicho" list="nichos-piloto" placeholder="Ex.: barbearia" {...campo("piloto_nicho")} />
            <datalist id="nichos-piloto">
              {dados.areas.nichos.map((n) => <option key={n} value={n} />)}
            </datalist>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="piloto-cidade">Cidade</Label>
            <Input id="piloto-cidade" list="cidades-piloto" placeholder="Ex.: Curitiba" {...campo("piloto_cidade")} />
            <datalist id="cidades-piloto">
              {dados.areas.cidades.map((c) => <option key={c} value={c} />)}
            </datalist>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="piloto-score">Score mínimo</Label>
            <Input id="piloto-score" type="number" min={0} max={100} {...campo("piloto_score_min")} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            disabled={area.length < 2 || buscando}
            onClick={() =>
              dispararBusca.mutate(`${cfg.piloto_nicho.trim()} em ${cfg.piloto_cidade.trim()}`)
            }
          >
            <Search className="size-4" />
            {buscando ? "Buscando no Google Maps..." : "Buscar novos leads nessa área"}
          </Button>
          <p className="text-[13px] text-muted-foreground">
            {area.length < 2
              ? "Preencha nicho e cidade para buscar no Google Maps."
              : statusBusca.data?.rodando
                ? statusBusca.data.mensagem
                : `${dados.disponiveis} lead(s) prontos para o piloto com a área salva.`}
          </p>
        </div>
      </Secao>

      <Secao
        numero={2}
        titulo="Ritmo e horário"
        descricao="Envios espaçados e só em horário comercial: parece gente, protege seu número."
      >
        <div className="grid gap-4 sm:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="hora-inicio">Começa às</Label>
            <Input id="hora-inicio" type="number" min={0} max={23} {...campo("piloto_hora_inicio")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="hora-fim">Para às</Label>
            <Input id="hora-fim" type="number" min={1} max={24} {...campo("piloto_hora_fim")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="int-min">Intervalo mín. (min)</Label>
            <Input id="int-min" type="number" min={1} {...campo("piloto_intervalo_min")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="int-max">Intervalo máx. (min)</Label>
            <Input id="int-max" type="number" min={1} {...campo("piloto_intervalo_max")} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-3 text-[15px]">
            <Switch
              checked={cfg.piloto_fim_de_semana === "1"}
              onCheckedChange={(v) => setCfg((a) => ({ ...a, piloto_fim_de_semana: v ? "1" : "0" }))}
            />
            Enviar também no fim de semana
          </label>
          <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <Clock className="size-3.5" />
            Limite de {dados.estado.limite_diario} envios/dia ·{" "}
            <Link to="/configuracoes" className="text-link hover:underline">alterar</Link>
          </p>
        </div>
      </Secao>

      <Secao
        numero={3}
        titulo="Respostas automáticas"
        descricao="Quando o cliente responde, a IA tira as dúvidas simples. Se ele quiser ver como ficaria, ela combina a prévia para o próximo dia útil e cria a tarefa para você. Fechamento, desconto e qualquer dúvida ela passa para você, e avisa no Telegram."
      >
        <label className="flex items-center gap-3 text-[15px]">
          <Switch
            checked={cfg.piloto_auto_resposta === "1"}
            onCheckedChange={(v) => setCfg((a) => ({ ...a, piloto_auto_resposta: v ? "1" : "0" }))}
          />
          Responder automaticamente
        </label>
        <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_180px]">
          <div className="space-y-1.5">
            <Label htmlFor="info-oferta">O que a IA pode dizer sobre a sua oferta</Label>
            <Textarea
              id="info-oferta"
              rows={4}
              placeholder={"Ex.: Site profissional a partir de R$ 990, pronto em 7 dias. Inclui domínio, botão de WhatsApp e Google Maps. Pagamento em até 3x."}
              {...campo("piloto_info_oferta")}
            />
            <p className="text-xs text-muted-foreground">
              A IA usa só o que estiver aqui. Sem preço escrito, ela passa a conversa para você quando perguntarem valores.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="max-resp">Respostas seguidas, no máximo</Label>
            <Input id="max-resp" type="number" min={1} max={20} {...campo("piloto_max_respostas")} />
            <p className="text-xs text-muted-foreground">Depois disso, a conversa passa para você.</p>
          </div>
        </div>
      </Secao>

      {/* barra de salvar só aparece com alteração pendente - nunca cobre o conteúdo à toa */}
      {mudou && (
        <div className="sticky bottom-4 z-10 flex items-center justify-between gap-3 rounded-full bg-foreground py-2 pr-2 pl-5 text-background shadow-2xl animate-in fade-in slide-in-from-bottom-2">
          <span className="text-sm font-medium">Você tem alterações não salvas</span>
          <div className="flex gap-1.5">
            <Button size="sm" variant="ghost" className="text-background/80 hover:bg-background/10 hover:text-background"
              onClick={() => setCfg(dados.config)}>
              Descartar
            </Button>
            <Button size="sm" disabled={salvar.isPending} onClick={handleSalvar}>
              <CheckCircle2 className="size-3.5" />
              {salvar.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </div>
      )}
    </>
  )
}

function Atividade({ eventos }: { eventos: EventoPiloto[] }) {
  return (
    <Secao titulo="Atividade" descricao="Tudo o que o piloto fez, do mais recente para o mais antigo.">
      {eventos.length === 0 ? (
        <p className="text-[15px] text-muted-foreground">Nada por aqui ainda. Ligue o piloto para começar.</p>
      ) : (
        <ol className="space-y-3">
          {eventos.map((evento) => {
            const info = ICONE_EVENTO[evento.tipo] ?? ICONE_EVENTO.erro
            const conteudo = (
              <div className="flex gap-3">
                <span className={cn("mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-secondary", info.cor)}>
                  {info.icone}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm">
                    <span className="font-medium">{info.rotulo}</span>
                    {evento.nome && <span className="text-muted-foreground"> · {evento.nome}</span>}
                  </p>
                  {evento.detalhe && <p className="line-clamp-2 text-[13px] text-muted-foreground">{evento.detalhe}</p>}
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">{formatarTempoRelativo(evento.em)}</span>
              </div>
            )
            return (
              <li key={evento.id}>
                {evento.place_id ? (
                  <Link
                    to={`/conversas/${encodeURIComponent(evento.place_id)}`}
                    className="-mx-2 block rounded-2xl px-2 py-1 transition-colors hover:bg-accent/60"
                  >
                    {conteudo}
                  </Link>
                ) : (
                  <div className="px-0 py-1">{conteudo}</div>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </Secao>
  )
}

export function PilotoPage() {
  const { data, isLoading } = usePainelPiloto()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="mx-auto w-full max-w-4xl space-y-5 px-4 py-8 sm:px-6">
        {isLoading || !data ? (
          <div className="space-y-5">
            <Skeleton className="h-64 rounded-[28px]" />
            <Skeleton className="h-48 rounded-[28px]" />
          </div>
        ) : (
          <>
            <Painel dados={data} />
            <PrecisaDeVoce dados={data} />
            <Previas dados={data} />
            <Formulario dados={data} />
            <Atividade eventos={data.eventos} />
          </>
        )}
      </main>
    </div>
  )
}
