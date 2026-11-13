import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useAdicionarDescadastro, useDescadastros } from "@/hooks/useEmail"

function ConteudoDescadastros() {
  const { data, isLoading } = useDescadastros(true)
  const adicionar = useAdicionarDescadastro()
  const [email, setEmail] = useState("")

  return (
    <>
      <DialogHeader>
        <DialogTitle>Lista de descadastros</DialogTitle>
        <DialogDescription>
          Quem pediu para sair nunca mais recebe e-mail do Seriax OS. Se alguém avisar por outro canal,
          adicione o endereço aqui.
        </DialogDescription>
      </DialogHeader>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (!email.includes("@")) return
          adicionar.mutate(email.trim(), { onSuccess: () => setEmail("") })
        }}
      >
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="pessoa@empresa.com.br"
          aria-label="E-mail a descadastrar"
        />
        <Button type="submit" disabled={!email.includes("@") || adicionar.isPending}>
          Adicionar
        </Button>
      </form>
      <div className="max-h-64 overflow-y-auto rounded-2xl bg-muted/50 p-2">
        {isLoading ? (
          <Skeleton className="h-16" />
        ) : !data || data.emails.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">Ninguém na lista ainda.</p>
        ) : (
          <ul className="divide-y divide-border text-sm">
            {data.emails.map((e) => (
              <li key={e} className="px-2 py-1.5">
                {e}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

export function DescadastrosDialog({ aberto, onFechar }: { aberto: boolean; onFechar: () => void }) {
  return (
    <Dialog open={aberto} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent>{aberto && <ConteudoDescadastros />}</DialogContent>
    </Dialog>
  )
}
