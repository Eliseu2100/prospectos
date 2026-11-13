import { History, PenLine } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PilulaStatus } from "@/components/shared/PilulaStatus"
import { formatarTempoRelativo } from "@/lib/formatters"
import { ORDEM_STATUS_EMAIL, ROTULO_FONTE_EMAIL, STATUS_EMAIL } from "@/lib/statusCanais"
import type { LeadEmail, StatusEmail } from "@/services/emailService"

interface TabelaLeadsEmailProps {
  leads: LeadEmail[]
  onEscrever: (lead: LeadEmail) => void
  onHistorico: (lead: LeadEmail) => void
  onMudarStatus: (lead: LeadEmail, status: StatusEmail) => void
}

export function TabelaLeadsEmail({ leads, onEscrever, onHistorico, onMudarStatus }: TabelaLeadsEmailProps) {
  return (
    <div className="overflow-x-auto rounded-2xl bg-card">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-xs text-muted-foreground">
            <th className="px-4 py-3 font-medium">Empresa</th>
            <th className="px-4 py-3 font-medium">E-mail</th>
            <th className="px-4 py-3 font-medium">Setor</th>
            <th className="px-4 py-3 font-medium">Cidade</th>
            <th className="px-4 py-3 font-medium">Fonte</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Último envio</th>
            <th className="px-4 py-3 text-right font-medium">Ações</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => {
            const bloqueado = lead.status === "descadastrado" || lead.status === "invalido"
            return (
              <tr key={lead.id} className="border-b border-border/60 last:border-0">
                <td className="max-w-[220px] px-4 py-3 font-medium">
                  <span className="block truncate" title={lead.empresa}>
                    {lead.empresa}
                  </span>
                </td>
                <td className="max-w-[220px] px-4 py-3 text-muted-foreground">
                  <span className="block truncate" title={lead.email}>
                    {lead.email}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{lead.setor ?? "—"}</td>
                <td className="px-4 py-3 text-muted-foreground">{lead.cidade ?? "—"}</td>
                <td className="px-4 py-3 text-muted-foreground">{ROTULO_FONTE_EMAIL[lead.fonte]}</td>
                <td className="px-4 py-3">
                  <Select value={lead.status} onValueChange={(v) => onMudarStatus(lead, v as StatusEmail)}>
                    <SelectTrigger size="sm" className="h-7 w-auto gap-1 border-0 bg-transparent px-0 shadow-none" aria-label={`Status de ${lead.empresa}`}>
                      <SelectValue>
                        <PilulaStatus rotulo={STATUS_EMAIL[lead.status].rotulo} tom={STATUS_EMAIL[lead.status].tom} />
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {ORDEM_STATUS_EMAIL.map((s) => (
                        <SelectItem key={s} value={s}>
                          {STATUS_EMAIL[s].rotulo}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                  {lead.ultimo_envio_em ? formatarTempoRelativo(lead.ultimo_envio_em) : "—"}
                  {lead.follow_ups_enviados > 0 && (
                    <span className="ml-1 text-xs">· {lead.follow_ups_enviados} follow-up(s)</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={bloqueado}
                      title={bloqueado ? "Contato bloqueado para envio" : undefined}
                      onClick={() => onEscrever(lead)}
                    >
                      <PenLine className="size-4" />
                      Escrever
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label={`Ver histórico de ${lead.empresa}`}
                      title="Histórico"
                      onClick={() => onHistorico(lead)}
                    >
                      <History className="size-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
