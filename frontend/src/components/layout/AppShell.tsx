import { Sidebar } from "@/components/layout/Sidebar"
import { TopBar } from "@/components/layout/TopBar"

/** Casco do app, nos moldes do dashboard de referência (Nozti): sidebar fixa
 * à esquerda + barra do topo, com o conteúdo de cada página passado como
 * children. Troca a barra superior antiga (Header.tsx), que ficou só para o
 * modal de conversa (ConversaPage), que é tela cheia por fora deste casco. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        {/* cada página rola o próprio conteúdo aqui dentro; páginas tipo
            ConversaPage (que já gerenciam o próprio scroll interno) usam
            h-full em vez de depender deste overflow */}
        <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
