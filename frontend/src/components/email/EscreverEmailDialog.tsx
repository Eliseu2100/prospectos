import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
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
import { useEnviarEmail } from "@/hooks/useEmail"
import { emailService, ROTULO_ESTILO_EMAIL, type EstiloEmail, type LeadEmail } from "@/services/emailService"

function ConteudoEscrever({ lead, onFechar }: { lead: LeadEmail; onFechar: () => void }) {
  const enviar = useEnviarEmail()
  const [assunto, setAssunto] = useState("")
  const [corpo, setCorpo] = useState("")
  const [provedor, setProvedor] = useState("")
  // primeiro contato: texto simples; quem já recebeu algo: marca com o PDF (dá para trocar a cada envio)
  const [estilo, setEstilo] = useState<EstiloEmail>(lead.ultimo_envio_em ? "marca_pdf" : "simples")
  const [rodada, setRodada] = useState(0)

  // Consulta (e não mutação disparada num efeito): o StrictMode do React solta o observador da mutação
  // no remonte e a tela ficava em "Gerando..." para sempre, mesmo com a resposta 200 (13/11/2026).
  // Sem refetch ao voltar para a janela, para não apagar o que o Eliseu já editou.
  const gerar = useQuery({
    queryKey: ["email-gerado", lead.id, rodada],
    queryFn: () => emailService.gerar(lead.id),
    staleTime: Infinity,
    gcTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  useEffect(() => {
    if (gerar.data) {
      setAssunto(gerar.data.assunto)
      setCorpo(gerar.data.corpo)
      setProvedor(gerar.data.provedor)
    }
  }, [gerar.data])

  useEffect(() => {
    if (gerar.error) toast.error((gerar.error as Error).message)
  }, [gerar.error])

  const gerando = gerar.isFetching
  function aoGerar() {
    setRodada((r) => r + 1)
  }

  function aoEnviar() {
    enviar.mutate({ id: lead.id, assunto: assunto.trim(), corpo: corpo.trim(), estilo }, { onSuccess: onFechar })
  }

  const ocupado = gerando || enviar.isPending

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
            disabled={gerando}
            placeholder={gerando ? "Gerando..." : ""}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="em-corpo">Mensagem</Label>
          <Textarea
            id="em-corpo"
            rows={10}
            value={corpo}
            onChange={(e) => setCorpo(e.target.value)}
            disabled={gerando}
            placeholder={gerando ? "Gerando o texto..." : ""}
            className="max-h-[45vh] overflow-y-auto"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="em-estilo">Como enviar</Label>
          <select
            id="em-estilo"
            value={estilo}
            onChange={(e) => setEstilo(e.target.value as EstiloEmail)}
            className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
          >
            {(Object.keys(ROTULO_ESTILO_EMAIL) as EstiloEmail[]).map((chave) => (
              <option key={chave} value={chave}>
                {ROTULO_ESTILO_EMAIL[chave]}
              </option>
            ))}
          </select>
        </div>
        <p className="text-xs text-muted-foreground">
          A assinatura e o pedido de descadastro entram automaticamente no envio.
          {provedor && ` Texto gerado por ${provedor}.`}
        </p>
      </div>
      <DialogFooter>
        <Button variant="outline" disabled={ocupado} onClick={aoGerar}>
          <RefreshCw className={gerando ? "size-4 animate-spin" : "size-4"} />
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
