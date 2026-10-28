import { BarChart3, ListTodo, MapPin, Search, Zap } from "lucide-react"
import { Link } from "react-router-dom"
import { Header } from "@/components/layout/Header"
import { InstagramIcon } from "@/components/icons/InstagramIcon"
import { VisaoGeralCombinada } from "@/components/dashboard/VisaoGeralCombinada"
import { FunilConversaoCombinado } from "@/components/dashboard/FunilConversaoCombinado"
import { BreakdownNichoCombinado } from "@/components/dashboard/BreakdownNichoCombinado"
import { NavCard } from "@/components/dashboard/NavCard"

export function DashboardPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6">
        <Link
          to="/leads?nova-busca=1"
          className="group flex flex-col gap-4 rounded-[28px] bg-card p-6 transition-colors hover:bg-accent/40 sm:flex-row sm:items-center sm:justify-between sm:p-8"
        >
          <div className="flex items-center gap-4">
            <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
              <Search className="size-7" />
            </div>
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">Buscar novos clientes</h2>
              <p className="text-[15px] text-muted-foreground">
                Escolha o tipo de negócio e a cidade, ou marque áreas no mapa. O Seriax OS encontra
                quem não tem site ou tem site ruim.
              </p>
            </div>
          </div>
          <span className="inline-flex h-11 shrink-0 items-center gap-2 self-start rounded-full bg-primary px-6 text-[15px] font-medium text-primary-foreground transition-colors group-hover:bg-primary/90 sm:self-auto">
            <Search className="size-4" />
            Nova busca
          </span>
        </Link>

        <VisaoGeralCombinada />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FunilConversaoCombinado />
          <BreakdownNichoCombinado />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <NavCard
            to="/sessao"
            titulo="Sessão de prospecção"
            descricao="Um lead por vez, do mais quente ao mais frio - modo foco"
            icone={<Zap className="size-5" />}
          />
          <NavCard
            to="/tarefas"
            titulo="Tarefas de hoje"
            descricao="Follow-ups vencidos e leads quentes com abordagem em 1 clique"
            icone={<ListTodo className="size-5" />}
          />
          <NavCard
            to="/leads"
            titulo="Leads do Maps"
            descricao="Lista, kanban e nova busca de leads do Google Maps"
            icone={<MapPin className="size-5" />}
          />
          <NavCard
            to="/instagram"
            titulo="Leads do Instagram"
            descricao="Analisar posts e gerenciar leads do Instagram"
            icone={<InstagramIcon className="size-5" />}
            destaqueInstagram
          />
          <NavCard
            to="/analytics"
            titulo="Analytics do Maps"
            descricao="Funil e conversão por nicho, só do Google Maps"
            icone={<BarChart3 className="size-5" />}
          />
        </div>
      </main>
    </div>
  )
}
