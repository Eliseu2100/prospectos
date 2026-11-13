import { ExternalLink, History } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PilulaStatus } from "@/components/shared/PilulaStatus"
import { followupVencidoOuHoje, formatarData } from "@/lib/formatters"
import { ORDEM_STATUS_LINKEDIN, STATUS_LINKEDIN } from "@/lib/statusCanais"
import type { LeadLinkedin, StatusLinkedin, TipoTextoLinkedin } from "@/services/linkedinService"

interface TabelaLeadsLinkedinProps {
  leads: LeadLinkedin[]
  onGerar: (lead: LeadLinkedin, tipo: TipoTextoLinkedin) => void
  onHistorico: (lead: LeadLinkedin) => void
  onMudarStatus: (lead: LeadLinkedin, status: StatusLinkedin) => void
}

export function TabelaLeadsLinkedin({ leads, onGerar, onHistorico, onMudarStatus }: TabelaLeadsLinkedinProps) {
  return (
    <div className="overflow-x-auto rounded-2xl bg-card">
      <table className="w-full min-w-[960px] text-left text-sm">
        <thead>
          <tr className="border-b border-border text-xs text-muted-foreground">
            <th className="px-4 py-3 font-medium">Nome</th>
            <th className="px-4 py-3 font-medium">Cargo e empresa</th>
            <th className="px-4 py-3 font-medium">Setor</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Próximo follow-up</th>
            <th className="px-4 py-3 text-right font-medium">Ações</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => (
            <tr key={lead.id} className="border-b border-border/60 last:border-0">
              <td className="max-w-[200px] px-4 py-3 font-medium">
                <span className="block truncate" title={lead.nome}>
                  {lead.nome}
                </span>
                {lead.cidade && <span className="block truncate text-xs font-normal text-muted-foreground">{lead.cidade}</span>}
              </td>
              <td className="max-w-[240px] px-4 py-3 text-muted-foreground">
                <span className="block truncate" title={[lead.cargo, lead.empresa].filter(Boolean).join(" · ")}>
                  {[lead.cargo, lead.empresa].filter(Boolean).join(" · ") || "—"}
                </span>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{lead.setor ?? "—"}</td>
              <td className="px-4 py-3">
                <Select value={lead.status} onValueChange={(v) => onMudarStatus(lead, v as StatusLinkedin)}>
                  <SelectTrigger size="sm" className="h-7 w-auto gap-1 border-0 bg-transparent px-0 shadow-none" aria-label={`Status de ${lead.nome}`}>
                    <SelectValue>
                      <PilulaStatus rotulo={STATUS_LINKEDIN[lead.status].rotulo} tom={STATUS_LINKEDIN[lead.status].tom} />
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {ORDEM_STATUS_LINKEDIN.map((s) => (
                      <SelectItem key={s} value={s}>
                        {STATUS_LINKEDIN[s].rotulo}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                {lead.proximo_followup ? (
                  <span
                    className={followupVencidoOuHoje(lead.proximo_followup) ? "font-medium text-warning-foreground" : "text-muted-foreground"}
                  >
                    {formatarData(lead.proximo_followup.slice(0, 10))}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-1.5">
                  <Button size="sm" variant="outline" onClick={() => onGerar(lead, "conexao")}>
                    Nota de conexão
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => onGerar(lead, "mensagem")}>
                    Mensagem
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => onGerar(lead, "followup")}>
                    Follow-up
                  </Button>
                  {lead.perfil_url && (
                    <Button size="icon-sm" variant="ghost" asChild>
                      <a
                        href={lead.perfil_url}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`Abrir perfil de ${lead.nome} em nova aba`}
                        title="Abrir perfil"
                      >
                        <ExternalLink className="size-4" />
                      </a>
                    </Button>
                  )}
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label={`Ver histórico de ${lead.nome}`}
                    title="Histórico"
                    onClick={() => onHistorico(lead)}
                  >
                    <History className="size-4" />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
