import { useEffect, useRef, useState } from "react"
import { Check, Copy, ExternalLink, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
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
import { useClipboard } from "@/hooks/useClipboard"
import { useGerarTextoLinkedin, useMudarStatusLinkedin } from "@/hooks/useLinkedin"
import { cn } from "@/lib/utils"
import type { LeadLinkedin, StatusLinkedin, TipoTextoLinkedin } from "@/services/linkedinService"

export interface PedidoTextoLinkedin {
  lead: LeadLinkedin
  tipo: TipoTextoLinkedin
}

const TITULO: Record<TipoTextoLinkedin, string> = {
  conexao: "Nota de conexão",
  mensagem: "Mensagem",
  followup: "Follow-up",
}

const STATUS_AO_ENVIAR: Record<TipoTextoLinkedin, StatusLinkedin> = {
  conexao: "conexao_enviada",
  mensagem: "mensagem_enviada",
  followup: "mensagem_enviada",
}

const LIMITE_PADRAO_CONEXAO = 300

function ConteudoTexto({ pedido, onFechar }: { pedido: PedidoTextoLinkedin; onFechar: () => void }) {
  const { lead, tipo } = pedido
  const gerar = useGerarTextoLinkedin()
  const mudarStatus = useMudarStatusLinkedin()
  const { copiado, copiar } = useClipboard()
  const [texto, setTexto] = useState("")
  const [provedor, setProvedor] = useState("")
  const [limite, setLimite] = useState<number | null>(tipo === "conexao" ? LIMITE_PADRAO_CONEXAO : null)
  const iniciou = useRef(false)

  function aoGerar() {
    gerar.mutate(
      { id: lead.id, tipo },
      {
        onSuccess: (res) => {
          setTexto(res.texto)
          setProvedor(res.provedor)
          setLimite(res.limite_caracteres)
        },
      }
    )
  }

  useEffect(() => {
    if (iniciou.current) return
    iniciou.current = true
    gerar.mutate(
      { id: lead.id, tipo },
      {
        onSuccess: (res) => {
          setTexto(res.texto)
          setProvedor(res.provedor)
          setLimite(res.limite_caracteres)
        },
      }
    )
  }, [gerar, lead.id, tipo])

  const estourou = tipo === "conexao" && limite !== null && texto.length > limite

  function aoMarcarEnviado() {
    mudarStatus.mutate({ id: lead.id, status: STATUS_AO_ENVIAR[tipo], texto: texto.trim() }, { onSuccess: onFechar })
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {TITULO[tipo]} para {lead.nome}
        </DialogTitle>
        <DialogDescription>
          {[lead.cargo, lead.empresa].filter(Boolean).join(" · ") || "Contato do LinkedIn"}. O app não envia
          nada ao LinkedIn: copie o texto e envie por lá.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-1.5">
        <Label htmlFor="li-texto">Texto</Label>
        <Textarea
          id="li-texto"
          rows={tipo === "conexao" ? 6 : 9}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={gerar.isPending}
          placeholder={gerar.isPending ? "Gerando o texto..." : ""}
          className="max-h-[45vh] overflow-y-auto"
        />
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{provedor && `Gerado por ${provedor}`}</span>
          <span className={cn("tabular-nums", estourou ? "font-medium text-destructive" : "text-muted-foreground")}>
            {texto.length}
            {tipo === "conexao" && limite !== null ? ` / ${limite}` : ""} caracteres
          </span>
        </div>
        {estourou && (
          <p className="text-xs text-destructive">
            Acima do limite da nota de conexão. Encurte o texto antes de enviar no LinkedIn.
          </p>
        )}
      </div>

      <DialogFooter className="sm:flex-wrap">
        {lead.perfil_url && (
          <Button variant="outline" asChild>
            <a href={lead.perfil_url} target="_blank" rel="noreferrer">
              <ExternalLink className="size-4" />
              Abrir perfil
            </a>
          </Button>
        )}
        <Button variant="outline" disabled={gerar.isPending} onClick={aoGerar}>
          <RefreshCw className={gerar.isPending ? "size-4 animate-spin" : "size-4"} />
          Gerar de novo
        </Button>
        <Button variant="outline" disabled={!texto.trim()} onClick={() => copiar(texto)}>
          {copiado ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copiado ? "Copiado" : "Copiar"}
        </Button>
        <Button
          disabled={!texto.trim() || estourou || gerar.isPending || mudarStatus.isPending}
          onClick={aoMarcarEnviado}
        >
          {mudarStatus.isPending ? "Salvando..." : "Marquei como enviado"}
        </Button>
      </DialogFooter>
    </>
  )
}

export function TextoLinkedinDialog({
  pedido,
  onFechar,
}: {
  pedido: PedidoTextoLinkedin | null
  onFechar: () => void
}) {
  return (
    <Dialog open={pedido !== null} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent className="sm:max-w-xl">
        {pedido && <ConteudoTexto key={`${pedido.lead.id}-${pedido.tipo}`} pedido={pedido} onFechar={onFechar} />}
      </DialogContent>
    </Dialog>
  )
}
