import { useEffect, useState } from "react"
import { CheckCircle2, MessageCircle, QrCode } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  useConectarWhatsapp,
  useConfigEnvio,
  useEstadoWhatsapp,
  useSalvarWhatsapp,
} from "@/hooks/useEnvio"
import type { EstadoWhatsapp } from "@/services/envioService"

const ROTULO_ESTADO: Record<EstadoWhatsapp, string> = {
  open: "Conectado",
  connecting: "Aguardando QR code",
  close: "Desconectado",
  inexistente: "Instância ainda não criada",
  indisponivel: "Evolution API fora do ar",
}

export function WhatsappEnvioCard() {
  const { data: config, isLoading } = useConfigEnvio()
  const salvar = useSalvarWhatsapp()
  const conectar = useConectarWhatsapp()
  const [qrcode, setQrcode] = useState<string | null>(null)
  const { data: estado } = useEstadoWhatsapp(qrcode !== null)

  const [url, setUrl] = useState("")
  const [instancia, setInstancia] = useState("")
  const [chave, setChave] = useState("")
  const [limite, setLimite] = useState("30")

  useEffect(() => {
    if (!config) return
    setUrl(config.whatsapp.url)
    setInstancia(config.whatsapp.instancia)
    setLimite(String(config.whatsapp.limite_diario))
  }, [config])

  // QR escaneado: some da tela assim que a Evolution reporta "open"
  useEffect(() => {
    if (estado?.estado === "open") setQrcode(null)
  }, [estado?.estado])

  if (isLoading || !config) return null

  const conectado = estado?.estado === "open"

  const handleSalvar = () =>
    salvar.mutate(
      {
        url: url.trim(),
        instancia: instancia.trim(),
        chave: chave.trim() || undefined,
        limite_diario: Number(limite),
      },
      { onSuccess: () => setChave("") }
    )

  const handleConectar = () =>
    conectar.mutate(undefined, { onSuccess: (res) => setQrcode(res.qrcode) })

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <MessageCircle className="size-4 text-muted-foreground" />
          <h3 className="font-medium">WhatsApp (Evolution API)</h3>
        </div>
        {conectado ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-medium text-success">
            <CheckCircle2 className="size-3.5" />
            Conectado · {config.whatsapp.enviados_hoje}/{config.whatsapp.limite_diario} hoje
          </span>
        ) : (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {estado ? ROTULO_ESTADO[estado.estado] : "Verificando..."}
          </span>
        )}
      </div>

      <p className="text-sm text-muted-foreground">
        Envia a mensagem direto do lead, sem abrir o WhatsApp Web. Precisa da
        Evolution API rodando no Docker (pasta <code>evolution/</code> do
        projeto). Use de preferência um número só pra prospecção: envio para
        quem não te conhece pode levar a bloqueio do número.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>URL da Evolution API</Label>
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:8080" />
        </div>
        <div className="space-y-1.5">
          <Label>Nome da instância</Label>
          <Input value={instancia} onChange={(e) => setInstancia(e.target.value)} placeholder="prospectos" />
        </div>
        <div className="space-y-1.5">
          <Label>Chave (AUTHENTICATION_API_KEY)</Label>
          <Input
            type="password"
            autoComplete="off"
            value={chave}
            onChange={(e) => setChave(e.target.value)}
            placeholder={
              config.whatsapp.chave_configurada
                ? `Salva · ${config.whatsapp.chave_mascarada}`
                : "A mesma do evolution/.env"
            }
          />
        </div>
        <div className="space-y-1.5">
          <Label>Limite de envios por dia</Label>
          <Input type="number" min={1} max={200} value={limite} onChange={(e) => setLimite(e.target.value)} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={salvar.isPending} onClick={handleSalvar}>
          {salvar.isPending ? "Salvando..." : "Salvar"}
        </Button>
        {!conectado && config.whatsapp.chave_configurada && (
          <Button size="sm" variant="outline" disabled={conectar.isPending} onClick={handleConectar}>
            <QrCode className="size-4" />
            {conectar.isPending ? "Gerando QR code..." : "Conectar (QR code)"}
          </Button>
        )}
      </div>

      {qrcode && (
        <div className="flex flex-col items-center gap-2 rounded-lg bg-white p-4">
          <img src={qrcode} alt="QR code para conectar o WhatsApp" className="size-56" />
          <p className="text-center text-xs text-neutral-600">
            No celular: WhatsApp → Aparelhos conectados → Conectar aparelho.
          </p>
        </div>
      )}
    </div>
  )
}
