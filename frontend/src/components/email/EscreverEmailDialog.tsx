import { useState } from "react"
import { Send } from "lucide-react"
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
import { useConfigEmail, useEnviarEmail } from "@/hooks/useEmail"
import { ROTULO_ESTILO_EMAIL, type EstiloEmail, type LeadEmail } from "@/services/emailService"

// Troca {empresa}, {setor} e {cidade} da mensagem padrão pelos dados do lead. Sem dado, a variável some.
function preencher(modelo: string, lead: LeadEmail) {
  return (modelo ?? "")
    .replace(/\{empresa\}/gi, lead.empresa ?? "")
    .replace(/\{setor\}/gi, lead.setor ?? "")
    .replace(/\{cidade\}/gi, lead.cidade ?? "")
}

function ConteudoEscrever({
  lead,
  onFechar,
  modeloAssunto,
  modeloCorpo,
}: {
  lead: LeadEmail
  onFechar: () => void
  modeloAssunto: string
  modeloCorpo: string
}) {
  const enviar = useEnviarEmail()
  const [assunto, setAssunto] = useState(() => preencher(modeloAssunto, lead))
  const [corpo, setCorpo] = useState(() => preencher(modeloCorpo, lead))
  // primeiro contato: texto simples; quem já recebeu algo: marca com o PDF (dá para trocar a cada envio)
  const [estilo, setEstilo] = useState<EstiloEmail>(lead.ultimo_envio_em ? "marca_pdf" : "simples")
  function aoEnviar() {
    enviar.mutate({ id: lead.id, assunto: assunto.trim(), corpo: corpo.trim(), estilo }, { onSuccess: onFechar })
  }

  const ocupado = enviar.isPending

  return (
    <>
      <DialogHeader>
        <DialogTitle>Escrever para {lead.empresa}</DialogTitle>
        <DialogDescription>
          {lead.email}. Escreva o texto: nada é enviado sem o seu clique em "Enviar".
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="em-assunto">Assunto</Label>
          <Input
            id="em-assunto"
            value={assunto}
            onChange={(e) => setAssunto(e.target.value)}
            placeholder="Assunto do e-mail"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="em-corpo">Mensagem</Label>
          <Textarea
            id="em-corpo"
            rows={10}
            value={corpo}
            onChange={(e) => setCorpo(e.target.value)}
            placeholder="Escreva a mensagem"
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
        </p>
      </div>
      <DialogFooter>
        <Button disabled={ocupado || !assunto.trim() || !corpo.trim()} onClick={aoEnviar}>
          <Send className="size-4" />
          {enviar.isPending ? "Enviando..." : "Enviar"}
        </Button>
      </DialogFooter>
    </>
  )
}

export function EscreverEmailDialog({ lead, onFechar }: { lead: LeadEmail | null; onFechar: () => void }) {
  const { data: config } = useConfigEmail()
  return (
    <Dialog open={lead !== null} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent className="sm:max-w-xl">
        {lead && config && (
          <ConteudoEscrever
            key={lead.id}
            lead={lead}
            onFechar={onFechar}
            modeloAssunto={config.smtp.modelo_assunto ?? ""}
            modeloCorpo={config.smtp.modelo_corpo ?? ""}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
