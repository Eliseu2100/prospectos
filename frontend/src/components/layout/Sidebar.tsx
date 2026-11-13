import { useEffect, useState } from "react"
import { Link, NavLink } from "react-router-dom"
import {
  BookOpen,
  Bot,
  ChevronLeft,
  ListTodo,
  Mail,
  MapPin,
  MessagesSquare,
  Settings,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { InstagramIcon } from "@/components/icons/InstagramIcon"
import { LinkedinIcon } from "@/components/icons/LinkedinIcon"
import { useMediaQuery } from "@/hooks/useMediaQuery"

const CHAVE_COLAPSADA = "seriax-sidebar-colapsada"

const NAV_PRINCIPAL = [
  { to: "/", icone: DashboardIcon, rotulo: "Dashboard", fim: true },
  { to: "/tarefas", icone: ListTodo, rotulo: "Tarefas" },
  { to: "/piloto", icone: Bot, rotulo: "Piloto" },
  { to: "/whatsapp", icone: MessagesSquare, rotulo: "WhatsApp" },
  { to: "/leads", icone: MapPin, rotulo: "Google Maps" },
  { to: "/instagram", icone: InstagramIcon, rotulo: "Instagram" },
  { to: "/email", icone: Mail, rotulo: "E-mail" },
  { to: "/linkedin", icone: LinkedinIcon, rotulo: "LinkedIn" },
]

const NAV_RODAPE = [
  { to: "/documentacao", icone: BookOpen, rotulo: "Documentação" },
  { to: "/configuracoes", icone: Settings, rotulo: "Configurações" },
]

function DashboardIcon({ className }: { className?: string }) {
  // mesmo ícone de "visão geral" usado na paleta de comando - evita importar
  // dois ícones diferentes pra dizer "dashboard"
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="2" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="2" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="2" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

function useSidebarColapsada() {
  const [colapsada, setColapsada] = useState(() => {
    try {
      return localStorage.getItem(CHAVE_COLAPSADA) === "1"
    } catch {
      return false
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(CHAVE_COLAPSADA, colapsada ? "1" : "0")
    } catch {
      // modo privado/bloqueio de storage: tudo bem, só não lembra na próxima vez
    }
  }, [colapsada])
  return [colapsada, setColapsada] as const
}

function ItemSidebar({
  to,
  icone: Icone,
  rotulo,
  fim,
  colapsada,
}: {
  to: string
  icone: React.ComponentType<{ className?: string }>
  rotulo: string
  fim?: boolean
  colapsada: boolean
}) {
  return (
    <NavLink
      to={to}
      end={fim}
      title={colapsada ? rotulo : undefined}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] font-medium transition-colors",
          colapsada && "justify-center px-0",
          isActive
            ? "bg-primary/12 text-primary"
            : "text-muted-foreground hover:bg-accent hover:text-foreground"
        )
      }
    >
      <Icone className="size-[18px] shrink-0" />
      {!colapsada && <span className="truncate">{rotulo}</span>}
    </NavLink>
  )
}

/** Navegação principal do Seriax OS, como a sidebar do dashboard de referência:
 * logo no topo, itens com ícone, recolhe pra só ícones (lembrado por sessão). */
export function Sidebar() {
  const [colapsadaPreferida, setColapsada] = useSidebarColapsada()
  // abaixo de md, a sidebar fica sempre só com ícones - não dá pra encolher
  // ainda mais nem respeitar a preferência de desktop sem quebrar o layout
  const ehMobile = useMediaQuery("(max-width: 767px)")
  const colapsada = colapsadaPreferida || ehMobile

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200",
        colapsada ? "w-[68px]" : "w-60"
      )}
    >
      <div className="flex h-14 items-center gap-2.5 px-4">
        <Link to="/" className="flex min-w-0 flex-1 items-center gap-2.5" aria-label="Seriax OS - início">
          <span className="relative flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-[10px] bg-primary/10">
            <img
              src="/logo-simbolo-fundo-claro.png"
              alt=""
              className="absolute left-1/2 top-[7%] h-[85%] w-auto -translate-x-1/2 object-contain dark:hidden"
            />
            <img
              src="/logo-simbolo-transparente.png"
              alt=""
              className="absolute left-1/2 top-[7%] hidden h-[85%] w-auto -translate-x-1/2 object-contain dark:block"
            />
          </span>
          {!colapsada && (
            <h1 className="truncate text-[15px] font-semibold tracking-tight text-sidebar-foreground">
              Seriax <span className="text-muted-foreground">OS</span>
            </h1>
          )}
        </Link>
        {!colapsada && (
          <button
            type="button"
            onClick={() => setColapsada(true)}
            title="Recolher menu"
            className="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <ChevronLeft className="size-4" />
          </button>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 py-2">
        {NAV_PRINCIPAL.map((item) => (
          <ItemSidebar key={item.to} {...item} colapsada={colapsada} />
        ))}
      </nav>

      <div className="flex flex-col gap-0.5 border-t border-sidebar-border px-3 py-2">
        {NAV_RODAPE.map((item) => (
          <ItemSidebar key={item.to} {...item} colapsada={colapsada} />
        ))}
        {colapsada && !ehMobile && (
          <button
            type="button"
            onClick={() => setColapsada(false)}
            title="Expandir menu"
            className="flex items-center justify-center rounded-xl px-3 py-2 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <ChevronLeft className="size-[18px] rotate-180" />
          </button>
        )}
      </div>
    </aside>
  )
}
