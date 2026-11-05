import { Link } from "react-router-dom"
import { Plus, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { BuscaEmAndamentoBarra } from "@/components/layout/BuscaEmAndamentoBarra"

/** Barra do topo: busca global (abre a paleta de comando ⌘K já existente no
 * app) + ação principal + tema. A sidebar cuida da navegação. */
export function TopBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/75 backdrop-blur-xl backdrop-saturate-150">
      <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
        <button
          type="button"
          onClick={() =>
            window.dispatchEvent(
              new KeyboardEvent("keydown", { key: "k", ctrlKey: true })
            )
          }
          className="flex h-9 min-w-0 max-w-sm flex-1 items-center gap-2 rounded-lg border border-input bg-card px-3 text-sm text-muted-foreground transition-colors hover:border-ring/40"
        >
          <Search className="size-4 shrink-0" />
          <span className="flex-1 truncate text-left">Buscar lead ou ir para uma página...</span>
          <kbd className="hidden shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] sm:inline">
            ⌘K
          </kbd>
        </button>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <Button size="sm" asChild>
            <Link to="/leads?nova-busca=1" aria-label="Nova busca de clientes">
              <Plus className="size-4" />
              <span className="hidden md:inline">Nova busca</span>
            </Link>
          </Button>
          <ThemeToggle />
        </div>
      </div>
      <BuscaEmAndamentoBarra />
    </header>
  )
}
