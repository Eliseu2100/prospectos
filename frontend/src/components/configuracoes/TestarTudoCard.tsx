import { useMutation } from "@tanstack/react-query"
import { CheckCircle2, ShieldCheck, XCircle } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { envioService } from "@/services/envioService"
import { cn } from "@/lib/utils"

/** Confere de verdade WhatsApp (envio + leitura), Telegram e chaves de IA. */
export function TestarTudoCard() {
  const testar = useMutation({
    mutationFn: envioService.testarTudo,
    onError: (erro: Error) => toast.error(erro.message),
  })
  const resultado = testar.data

  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-muted-foreground" />
          <h3 className="font-medium">Testar tudo</h3>
        </div>
        <Button size="sm" disabled={testar.isPending} onClick={() => testar.mutate()}>
          {testar.isPending ? "Testando (até 10 s)..." : "Testar agora"}
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        Confere se o WhatsApp está conectado, manda uma mensagem de teste para o seu próprio número
        pelo mesmo caminho do CRM (aparece no chat "Você"), verifica se ela volta na leitura das
        conversas e testa o Telegram. Não mexe em nenhum lead.
      </p>

      {resultado && (
        <ul className="space-y-2">
          {resultado.itens.map((item) => (
            <li key={item.nome} className="flex gap-2.5 rounded-xl bg-muted/60 px-3 py-2.5">
              {item.ok ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
              ) : (
                <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
              )}
              <div className="min-w-0">
                <p className={cn("text-sm font-medium", !item.ok && "text-destructive")}>{item.nome}</p>
                <p className="text-[13px] text-muted-foreground">{item.detalhe}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
