import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { formatarDataHora } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import type { MensagemHistorico } from "@/services/emailService"

interface HistoricoMensagensDialogProps {
  aberto: boolean
  onFechar: () => void
  titulo: string
  mensagens: MensagemHistorico[] | undefined
  carregando: boolean
}

/** Histórico de mensagens de um lead (e-mail ou LinkedIn): vendedor à direita,
 * lead à esquerda. Só leitura. */
export function HistoricoMensagensDialog({
  aberto,
  onFechar,
  titulo,
  mensagens,
  carregando,
}: HistoricoMensagensDialogProps) {
  return (
    <Dialog open={aberto} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Histórico</DialogTitle>
          <DialogDescription>{titulo}</DialogDescription>
        </DialogHeader>
        <div className="max-h-[60vh] space-y-2 overflow-y-auto">
          {carregando ? (
            <Skeleton className="h-20" />
          ) : !mensagens || mensagens.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Nenhuma mensagem registrada ainda.</p>
          ) : (
            mensagens.map((m, i) => (
              <div
                key={i}
                className={cn(
                  "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm",
                  m.autor === "vendedor"
                    ? "ml-auto bg-primary/12 text-foreground"
                    : "mr-auto bg-muted text-foreground"
                )}
              >
                <p className="whitespace-pre-wrap break-words">{m.texto}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {m.autor === "vendedor" ? "Você" : "Lead"} · {formatarDataHora(m.enviada_em)}
                </p>
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
