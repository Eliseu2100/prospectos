import { useEffect, useRef, useState } from "react"
import { RefreshCw, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useEnviarEmail, useGerarEmail } from "@/hooks/useEmail"
import type { LeadEmail } from "@/services/emailService"

function ConteudoEscrever({ lead, onFechar }: { lead: LeadEmail; onFechar: () => void }) {
  const gerar = useGerarEmail()
  const enviar = useEnviarEmail()
  const [assunto, setAssunto] = useState("")
  const [corpo, setCorpo] = useState("")
  const [provedor, setProvedor] = useState("")
  const iniciou = useRef(false)

  function aoGerar() {
    gerar.mutate(lead.id, {
      onSuccess: (res) => {
        setAssunto(res.assunto)
        setCorpo(res.corpo)
        setProvedor(res.provedor)
      },
    })
  }

  useEffect(() => {
    if (iniciou.current) return
    iniciou.current = true
    gerar.mutate(lead.id, {
      onSuccess: (res) => {
        setAssunto(res.assunto)
        setCorpo(res.corpo)
        setProvedor(res.provedor)
      },
    })
  }, [gerar, lead.id])

  function aoEnviar() {
    enviar.mutate({ id: lead.id, assunto: assunto.trim(), corpo: corpo.trim() }, { onSuccess: onFechar })
  }

  const ocupado = gerar.isPending || enviar.isPending

  return (
    <>
      <DialogHeader>
        <DialogTitle>Escrever para {lead.empresa}</DialogTitle>
        <DialogDescription>
          {lead.email}. Leia e ajuste o texto: nada é enviado sem o seu clique em "Enviar".
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="em-assunto">Assunto</Label>
          <Input
            id="em-assunto"
            value={assunto}
            onChange={(e) => setAssunto(e.target.value)}
            disabled={gerar.isPending}
            placeholder={gerar.isPending ? "Gerando..." : ""}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="em-corpo">Mensagem</Label>
          <Textarea
            id="em-corpo"
            rows={10}
            value={corpo}
            onChange={(e) => setCorpo(e.target.value)}
            disabled={gerar.isPending}
            placeholder={gerar.isPending ? "Gerando o texto..." : ""}
            className="max-h-[45vh] overflow-y-auto"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          A assinatura e o pedido de descadastro entram automaticamente no envio.
          {provedor && ` Texto gerado por ${provedor}.`}
        </p>
      </div>
      <DialogFooter>
        <Button variant="outline" disabled={ocupado} onClick={aoGerar}>
          <RefreshCw className={gerar.isPending ? "size-4 animate-spin" : "size-4"} />
          Gerar de novo
        </Button>
        <Button disabled={ocupado || !assunto.trim() || !corpo.trim()} onClick={aoEnviar}>
          <Send className="size-4" />
          {enviar.isPending ? "Enviando..." : "Enviar"}
        </Button>
      </DialogFooter>
    </>
  )
}

export function EscreverEmailDialog({ lead, onFechar }: { lead: LeadEmail | null; onFechar: () => void }) {
  return (
    <Dialog open={lead !== null} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent className="sm:max-w-xl">
        {lead && <ConteudoEscrever key={lead.id} lead={lead} onFechar={onFechar} />}
      </DialogContent>
    </Dialog>
  )
}
