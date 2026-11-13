import { useRef, useState } from "react"
import { FileUp, Upload } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useImportarCsvLinkedin } from "@/hooks/useLinkedin"

export function ImportarCsvCard() {
  const importar = useImportarCsvLinkedin()
  const [csv, setCsv] = useState("")
  const [nomeArquivo, setNomeArquivo] = useState("")
  const inputArquivo = useRef<HTMLInputElement>(null)

  async function aoEscolherArquivo(e: React.ChangeEvent<HTMLInputElement>) {
    const arquivo = e.target.files?.[0]
    if (!arquivo) return
    try {
      setCsv(await arquivo.text())
      setNomeArquivo(arquivo.name)
    } catch {
      toast.error("Não consegui ler esse arquivo.")
    }
    e.target.value = ""
  }

  function aoImportar() {
    importar.mutate(csv, {
      onSuccess: () => {
        setCsv("")
        setNomeArquivo("")
      },
    })
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-card p-5">
      <div className="flex items-center gap-2">
        <Upload className="size-4 text-muted-foreground" />
        <h3 className="font-medium">Importar contatos (CSV)</h3>
      </div>
      <p className="text-sm text-muted-foreground">
        Envie o arquivo ou cole o texto. Colunas aceitas: nome, cargo, empresa, link do perfil, setor e cidade.
        Exportações do Sales Navigator e do LinkedIn, em português ou inglês, também funcionam.
      </p>

      <input
        ref={inputArquivo}
        type="file"
        accept=".csv,text/csv,text/plain"
        className="hidden"
        onChange={aoEscolherArquivo}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => inputArquivo.current?.click()}>
          <FileUp className="size-4" />
          Escolher arquivo
        </Button>
        {nomeArquivo && <span className="text-xs text-muted-foreground">{nomeArquivo}</span>}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="li-csv">Ou cole o conteúdo aqui</Label>
        <Textarea
          id="li-csv"
          rows={4}
          value={csv}
          onChange={(e) => setCsv(e.target.value)}
          placeholder={"nome,cargo,empresa,link do perfil\nMaria Souza,Sócia,Clínica Aurora,https://www.linkedin.com/in/maria"}
          className="max-h-48 overflow-y-auto font-mono text-xs"
        />
      </div>

      <div className="flex justify-end">
        <Button size="sm" disabled={!csv.trim() || importar.isPending} onClick={aoImportar}>
          {importar.isPending ? "Importando..." : "Importar"}
        </Button>
      </div>
    </div>
  )
}
