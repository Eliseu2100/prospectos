import { SelectComVazio } from "@/components/filters/SelectComVazio"
import type { FiltrosLeads } from "@/types/lead"

interface OrdenacaoLeadsSelectProps {
  valor: FiltrosLeads["ordenar"]
  onChange: (valor: FiltrosLeads["ordenar"]) => void
}

export function OrdenacaoLeadsSelect({ valor, onChange }: OrdenacaoLeadsSelectProps) {
  return (
    <SelectComVazio
      valor={valor}
      onChange={(v) => onChange(v as FiltrosLeads["ordenar"])}
      opcoes={[
        { valor: "score", label: "Melhor score" },
        { valor: "encontrados", label: "Encontrados por último" },
      ]}
      labelVazio="Atividade recente"
      placeholder="Ordenar por"
      className="w-[190px]"
    />
  )
}
