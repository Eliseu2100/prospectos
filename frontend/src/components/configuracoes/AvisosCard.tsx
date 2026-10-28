import { useEffect, useState } from "react"
import { Bell, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useConfigEnvio, useSalvarAvisos, useTestarAviso } from "@/hooks/useEnvio"

/** Para onde vão os avisos "cliente respondeu", "precisa de você" e "prévia
 * combinada": Telegram (card abaixo) e/ou um número de WhatsApp seu. */
export function AvisosCard() {
  const { data: config, isLoading } = useConfigEnvio()
  const salvar = useSalvarAvisos()
  const testar = useTestarAviso()
  const [numero, setNumero] = useState("")

  useEffect(() => {
    if (config) setNumero(config.avisos.whatsapp_numero)
  }, [config])

  if (isLoading || !config) return null

  const { whatsapp_numero, telegram_pronto } = config.avisos
  const algumCanal = telegram_pronto || Boolean(whatsapp_numero)

  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bell className="size-4 text-muted-foreground" />
          <h3 className="font-medium">Avisos para você</h3>
        </div>
        {algumCanal ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">
            <CheckCircle2 className="size-3.5" />
            {[telegram_pronto && "Telegram", whatsapp_numero && "WhatsApp"].filter(Boolean).join(" + ")}
          </span>
        ) : (
          <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
            Nenhum canal
          </span>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Você recebe um aviso quando um cliente que está com você responde, quando o piloto passa
        uma conversa para você (preço, fechamento, áudio) e quando combina uma prévia.
      </p>

      <div className="space-y-1.5">
        <Label htmlFor="aviso-numero">WhatsApp que recebe os avisos (opcional)</Label>
        <div className="flex gap-2">
          <Input
            id="aviso-numero"
            inputMode="tel"
            value={numero}
            onChange={(e) => setNumero(e.target.value)}
            placeholder="Seu número pessoal, ex.: 11 91234-5678"
          />
          <Button size="sm" disabled={salvar.isPending} onClick={() => salvar.mutate(numero.trim())}>
            Salvar
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Use um número <strong>diferente</strong> do conectado no Seriax OS: o WhatsApp não toca
          para mensagens que você manda para você mesmo. Deixe vazio para avisar só pelo Telegram.
        </p>
      </div>

      <Button
        size="sm"
        variant="outline"
        className="w-fit"
        disabled={!algumCanal || testar.isPending}
        onClick={() => testar.mutate(undefined)}
      >
        <Bell className="size-3.5" />
        {testar.isPending ? "Enviando..." : "Enviar aviso de teste"}
      </Button>
    </div>
  )
}
