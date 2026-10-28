import { Link, NavLink } from "react-router-dom"
import { BookOpen, Bot, ListTodo, MapPin, MessagesSquare, Plus, Settings, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { InstagramIcon } from "@/components/icons/InstagramIcon"

interface HeaderProps {
  onNovaBusca?: () => void
  onVerIgnorados?: () => void
}

function ItemNav({
  to,
  icone,
  ariaLabel,
  children,
}: {
  to: string
  icone: React.ReactNode
  ariaLabel?: string
  children?: React.ReactNode
}) {
  return (
    <NavLink
      to={to}
      aria-label={ariaLabel}
      className={({ isActive }) =>
        cn(
          "inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium transition-colors",
          isActive
            ? "bg-foreground text-background"
            : "text-foreground/70 hover:bg-accent hover:text-foreground"
        )
      }
    >
      {icone}
      {children && <span className="hidden sm:inline">{children}</span>}
    </NavLink>
  )
}

export function Header({ onNovaBusca, onVerIgnorados }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/75 backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2" aria-label="Seriax OS - início">
          <img src="/logo-icon.svg" alt="" className="size-8 rounded-[9px] ring-1 ring-black/5 dark:ring-white/10" />
          <h1 className="text-[17px] font-semibold tracking-tight">
            Seriax <span className="text-muted-foreground">OS</span>
          </h1>
        </Link>

        <nav className="flex items-center gap-0.5 overflow-x-auto">
          <ItemNav to="/tarefas" icone={<ListTodo className="size-4" />}>
            Tarefas
          </ItemNav>
          <ItemNav to="/piloto" icone={<Bot className="size-4" />}>
            Piloto
          </ItemNav>
          <ItemNav to="/whatsapp" icone={<MessagesSquare className="size-4" />}>
            WhatsApp
          </ItemNav>
          <ItemNav to="/leads" icone={<MapPin className="size-4" />}>
            Google Maps
          </ItemNav>
          <ItemNav to="/instagram" icone={<InstagramIcon className="size-4" />}>
            Instagram
          </ItemNav>
          <ItemNav to="/documentacao" icone={<BookOpen className="size-4" />} ariaLabel="Documentação" />
          {onVerIgnorados && (
            <Button variant="ghost" size="sm" onClick={onVerIgnorados} aria-label="Ignorados">
              <Trash2 className="size-4" />
              <span className="hidden sm:inline">Ignorados</span>
            </Button>
          )}
          {onNovaBusca && (
            <Button size="sm" onClick={onNovaBusca}>
              <Plus className="size-4" />
              <span className="hidden sm:inline">Nova busca</span>
            </Button>
          )}
          <ItemNav
            to="/configuracoes"
            icone={<Settings className="size-4" />}
            ariaLabel="Configurações"
          />
          <ThemeToggle />
        </nav>
      </div>
    </header>
  )
}
