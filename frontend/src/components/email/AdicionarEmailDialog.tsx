import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useAdicionarLeadEmail } from "@/hooks/useEmail"

function FormularioEmail({ onFechar }: { onFechar: () => void }) {
  const adicionar = useAdicionarLeadEmail()
  const [empresa, setEmpresa] = useState("")
  const [email, setEmail] = useState("")
  const [setor, setSetor] = useState("")
  const [cidade, setCidade] = useState("")
  const [siteUrl, setSiteUrl] = useState("")

  const valido = empresa.trim() && email.includes("@")

  function aoAdicionar() {
    adicionar.mutate(
      {
        empresa: empresa.trim(),
        email: email.trim(),
        ...(setor.trim() ? { setor: setor.trim() } : {}),
        ...(cidade.trim() ? { cidade: cidade.trim() } : {}),
        ...(siteUrl.trim() ? { site_url: siteUrl.trim() } : {}),
      },
      { onSuccess: onFechar }
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Adicionar e-mail</DialogTitle>
        <DialogDescription>Cadastre um contato à mão.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="ae-empresa">Empresa</Label>
          <Input id="ae-empresa" value={empresa} onChange={(e) => setEmpresa(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ae-email">E-mail</Label>
          <Input id="ae-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="ae-setor">Setor (opcional)</Label>
            <Input id="ae-setor" value={setor} onChange={(e) => setSetor(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ae-cidade">Cidade (opcional)</Label>
            <Input id="ae-cidade" value={cidade} onChange={(e) => setCidade(e.target.value)} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ae-site">Site (opcional)</Label>
          <Input id="ae-site" value={siteUrl} onChange={(e) => setSiteUrl(e.target.value)} placeholder="https://" />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
        <Button disabled={!valido || adicionar.isPending} onClick={aoAdicionar}>
          {adicionar.isPending ? "Salvando..." : "Adicionar"}
        </Button>
      </DialogFooter>
    </>
  )
}

export function AdicionarEmailDialog({ aberto, onFechar }: { aberto: boolean; onFechar: () => void }) {
  return (
    <Dialog open={aberto} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent>{aberto && <FormularioEmail onFechar={onFechar} />}</DialogContent>
    </Dialog>
  )
}
