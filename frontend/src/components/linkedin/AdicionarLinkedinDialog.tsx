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
import { useAdicionarLeadLinkedin } from "@/hooks/useLinkedin"

function FormularioLinkedin({ onFechar }: { onFechar: () => void }) {
  const adicionar = useAdicionarLeadLinkedin()
  const [nome, setNome] = useState("")
  const [cargo, setCargo] = useState("")
  const [empresa, setEmpresa] = useState("")
  const [perfilUrl, setPerfilUrl] = useState("")
  const [setor, setSetor] = useState("")
  const [cidade, setCidade] = useState("")

  function opcional(valor: string) {
    return valor.trim() || undefined
  }

  function aoAdicionar() {
    adicionar.mutate(
      {
        nome: nome.trim(),
        cargo: opcional(cargo),
        empresa: opcional(empresa),
        perfil_url: opcional(perfilUrl),
        setor: opcional(setor),
        cidade: opcional(cidade),
      },
      { onSuccess: onFechar }
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Adicionar contato</DialogTitle>
        <DialogDescription>Cadastre uma pessoa do LinkedIn à mão.</DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="al-nome">Nome</Label>
          <Input id="al-nome" value={nome} onChange={(e) => setNome(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="al-cargo">Cargo (opcional)</Label>
            <Input id="al-cargo" value={cargo} onChange={(e) => setCargo(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="al-empresa">Empresa (opcional)</Label>
            <Input id="al-empresa" value={empresa} onChange={(e) => setEmpresa(e.target.value)} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="al-perfil">Link do perfil (opcional)</Label>
          <Input
            id="al-perfil"
            value={perfilUrl}
            onChange={(e) => setPerfilUrl(e.target.value)}
            placeholder="https://www.linkedin.com/in/..."
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="al-setor">Setor (opcional)</Label>
            <Input id="al-setor" value={setor} onChange={(e) => setSetor(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="al-cidade">Cidade (opcional)</Label>
            <Input id="al-cidade" value={cidade} onChange={(e) => setCidade(e.target.value)} />
          </div>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
        <Button disabled={!nome.trim() || adicionar.isPending} onClick={aoAdicionar}>
          {adicionar.isPending ? "Salvando..." : "Adicionar"}
        </Button>
      </DialogFooter>
    </>
  )
}

export function AdicionarLinkedinDialog({ aberto, onFechar }: { aberto: boolean; onFechar: () => void }) {
  return (
    <Dialog open={aberto} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent>{aberto && <FormularioLinkedin onFechar={onFechar} />}</DialogContent>
    </Dialog>
  )
}
