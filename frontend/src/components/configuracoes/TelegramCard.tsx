import { useState } from "react"
import { CheckCircle2, ExternalLink, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  useConfigEnvio,
  useDetectarChatTelegram,
  useEnviarResumoTelegram,
  useSalvarTelegram,
  useTestarTelegram,
} from "@/hooks/useEnvio"

export function TelegramCard() {
  const { data: config, isLoading } = useConfigEnvio()
  const salvar = useSalvarTelegram()
  const detectar = useDetectarChatTelegram()
  const testar = useTestarTelegram()
  const resumo = useEnviarResumoTelegram()
  const [token, setToken] = useState("")

  if (isLoading || !config) return null

  const { token_configurado, token_mascarado, chat_id } = config.telegram
  const pronto = token_configurado && Boolean(chat_id)

  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Send className="size-4 text-muted-foreground" />
          <h3 className="font-medium">Telegram (avisos pra você)</h3>
        </div>
        {pronto ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">
            <CheckCircle2 className="size-3.5" />
            Pronto
          </span>
        ) : (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            Não configurado
          </span>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Receba no Telegram o resumo do dia (follow-ups pendentes, leads novos e
        envios). Bots do Telegram não podem puxar conversa com quem nunca falou
        com eles, por isso aqui o bot avisa você, e não aborda leads.
      </p>

      <ol className="list-decimal space-y-1 pl-5 text-xs text-muted-foreground">
        <li>
          No Telegram, fale com o{" "}
          <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="underline">
            @BotFather
          </a>
          , mande <code>/newbot</code> e copie o token.
        </li>
        <li>Cole o token abaixo e salve.</li>
        <li>
          Abra o seu bot, mande <code>/start</code> e clique em "Detectar chat".
        </li>
      </ol>

      <div className="space-y-1.5">
        <Label>Token do bot</Label>
        <div className="flex gap-2">
          <Input
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={token_configurado ? `Salvo · ${token_mascarado}` : "123456789:ABC..."}
          />
          <Button
            size="sm"
            disabled={!token.trim() || salvar.isPending}
            onClick={() => salvar.mutate({ token: token.trim() }, { onSuccess: () => setToken("") })}
          >
            Salvar
          </Button>
        </div>
        {chat_id && <p className="text-xs text-muted-foreground">Chat vinculado: {chat_id}</p>}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={!token_configurado || detectar.isPending}
          onClick={() => detectar.mutate(undefined)}
        >
          Detectar chat
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!pronto || testar.isPending}
          onClick={() => testar.mutate(undefined)}
        >
          Enviar teste
        </Button>
        <Button size="sm" disabled={!pronto || resumo.isPending} onClick={() => resumo.mutate(undefined)}>
          {resumo.isPending ? "Enviando..." : "Enviar resumo do dia"}
        </Button>
      </div>

      <a
        href="https://core.telegram.org/bots/tutorial"
        target="_blank"
        rel="noreferrer"
        className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:underline"
      >
        <ExternalLink className="size-3" />
        Como criar um bot
      </a>
    </div>
  )
}
