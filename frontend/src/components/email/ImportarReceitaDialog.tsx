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
import { useImportarReceita } from "@/hooks/useEmail"

function FormularioReceita({ onFechar }: { onFechar: () => void }) {
  const importar = useImportarReceita()
  const [arquivo, setArquivo] = useState("")
  const [cnaes, setCnaes] = useState("")
  const [uf, setUf] = useState("")
  const [municipio, setMunicipio] = useState("")
  const [limite, setLimite] = useState("")

  const listaCnaes = cnaes
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean)
  const valido = arquivo.trim() && listaCnaes.length > 0 && uf.trim().length === 2

  function aoImportar() {
    importar.mutate(
      {
        arquivo: arquivo.trim(),
        cnaes: listaCnaes,
        uf: uf.trim().toUpperCase(),
        ...(municipio.trim() ? { municipio: municipio.trim() } : {}),
        ...(Number(limite) > 0 ? { limite: Number(limite) } : {}),
      },
      { onSuccess: onFechar }
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Importar da base da Receita</DialogTitle>
        <DialogDescription>
          Lê o arquivo de Estabelecimentos da Receita Federal que já está no seu computador e traz só as
          empresas dos CNAEs e da região que você indicar.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="rf-arquivo">Caminho do arquivo</Label>
          <Input
            id="rf-arquivo"
            value={arquivo}
            onChange={(e) => setArquivo(e.target.value)}
            placeholder="C:\dados\Estabelecimentos0.csv"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rf-cnaes">CNAEs (separados por vírgula)</Label>
          <Input id="rf-cnaes" value={cnaes} onChange={(e) => setCnaes(e.target.value)} placeholder="8630504, 9602501" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="rf-uf">UF</Label>
            <Input id="rf-uf" maxLength={2} value={uf} onChange={(e) => setUf(e.target.value)} placeholder="SP" />
          </div>
          <div className="col-span-2 space-y-1.5">
            <Label htmlFor="rf-municipio">Município (opcional)</Label>
            <Input id="rf-municipio" value={municipio} onChange={(e) => setMunicipio(e.target.value)} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rf-limite">Limite de e-mails (opcional)</Label>
          <Input id="rf-limite" type="number" min={1} value={limite} onChange={(e) => setLimite(e.target.value)} />
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
        <Button disabled={!valido || importar.isPending} onClick={aoImportar}>
          {importar.isPending ? "Importando..." : "Importar"}
        </Button>
      </DialogFooter>
    </>
  )
}

export function ImportarReceitaDialog({ aberto, onFechar }: { aberto: boolean; onFechar: () => void }) {
  return (
    <Dialog open={aberto} onOpenChange={(v) => !v && onFechar()}>
      <DialogContent>{aberto && <FormularioReceita onFechar={onFechar} />}</DialogContent>
    </Dialog>
  )
}
