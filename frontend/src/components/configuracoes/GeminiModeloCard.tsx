import { Sparkles } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useConfigEnvio, useSalvarModeloGemini } from "@/hooks/useEnvio"

export function GeminiModeloCard() {
  const { data: config, isLoading } = useConfigEnvio()
  const salvar = useSalvarModeloGemini()

  if (isLoading || !config) return null

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-muted-foreground" />
        <h3 className="font-medium">Modelo do Gemini</h3>
      </div>
      <p className="text-sm text-muted-foreground">
        O Pro escreve mensagens e analisa conversas melhor, mas a cota gratuita
        da API é bem menor. Se ela acabar, o sistema passa sozinho para Groq ou
        NVIDIA.
      </p>
      <Select value={config.gemini.modelo} onValueChange={(modelo) => salvar.mutate(modelo)}>
        <SelectTrigger className="w-full sm:w-[340px]">
          <SelectValue placeholder="Escolha o modelo" />
        </SelectTrigger>
        <SelectContent>
          {config.gemini.opcoes.map((opcao) => (
            <SelectItem key={opcao.valor} value={opcao.valor}>
              {opcao.rotulo}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
