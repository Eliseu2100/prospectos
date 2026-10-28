import { Link, NavLink } from "react-router-dom"
import { BookOpen, ListTodo, MapPin, MessagesSquare, Plus, Settings, Trash2 } from "lucide-react"
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
          "inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors",
          isActive
            ? "bg-accent text-foreground"
            : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
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
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo-icon.svg" alt="ProspectOS" className="size-9" />
          <h1 className="text-lg font-semibold tracking-tight sm:text-xl">
            ProspectOS
          </h1>
        </Link>

        <nav className="flex items-center gap-1">
          <ItemNav to="/tarefas" icone={<ListTodo className="size-4" />}>
            Tarefas
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
          <ItemNav to="/documentacao" icone={<BookOpen className="size-4" />}>
            Documentação
          </ItemNav>
          {onVerIgnorados && (
            <Button variant="ghost" size="sm" onClick={onVerIgnorados}>
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
