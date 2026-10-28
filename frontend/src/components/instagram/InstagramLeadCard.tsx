import { Archive, Copy, Users } from "lucide-react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useClipboard } from "@/hooks/useClipboard"
import { useInstagramLeadMutations } from "@/hooks/useInstagramLeadMutations"
import { PrioridadeBadge } from "@/components/instagram/PrioridadeBadge"
import { TagChips } from "@/components/leads/TagChips"
import { FollowupBadge } from "@/components/leads/FollowupBadge"
import { LeadDificilBadge } from "@/components/leads/LeadDificilBadge"
import { LABEL_STATUS } from "@/lib/constants"
import { followupVencidoOuHoje } from "@/lib/formatters"
import { STATUS_VALIDOS, type StatusLead } from "@/types/lead"
import type { LeadInstagram } from "@/types/instagram"

interface InstagramLeadCardProps {
  lead: LeadInstagram
  selecionado: boolean
  onAlternarSelecao: () => void
  onAbrirDetalhe: () => void
}

export function InstagramLeadCard({
  lead,
  selecionado,
  onAlternarSelecao,
  onAbrirDetalhe,
}: InstagramLeadCardProps) {
  const { copiado, copiar } = useClipboard()
  const { atualizarStatus, ignorar } = useInstagramLeadMutations(
    lead.id,
    lead.post_id
  )
  const vencido = followupVencidoOuHoje(lead.proximo_followup)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      role="button"
      tabIndex={0}
      onClick={onAbrirDetalhe}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onAbrirDetalhe()
      }}
      className={cn(
        "relative flex cursor-pointer flex-col gap-3 rounded-2xl bg-card p-4 transition-colors hover:bg-accent/40",
        vencido && "ring-2 ring-warning",
        selecionado && "ring-2 ring-primary"
      )}
    >
      <input
        type="checkbox"
        checked={selecionado}
        onChange={() => onAlternarSelecao()}
        onClick={(e) => e.stopPropagation()}
        aria-label={`Selecionar @${lead.username}`}
        className="absolute right-3 top-3 size-4 cursor-pointer accent-primary"
      />

      <div className="flex items-start justify-between gap-2 pr-6">
        <div className="min-w-0">
          <h3 className="truncate font-medium leading-snug">
            @{lead.username}
          </h3>
          {lead.full_name && (
            <p className="truncate text-sm text-muted-foreground">
              {lead.full_name}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          <PrioridadeBadge prioridade={lead.prioridade} />
          {vencido && <FollowupBadge />}
          {lead.lead_dificil && <LeadDificilBadge />}
        </div>
      </div>

      <div
        className="flex flex-wrap items-center gap-2"
        onClick={(e) => e.stopPropagation()}
      >
        <Select
          value={lead.status}
          onValueChange={(v) => atualizarStatus.mutate(v as StatusLead)}
        >
          <SelectTrigger className="h-8 w-[140px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_VALIDOS.map((s) => (
              <SelectItem key={s} value={s}>
                {LABEL_STATUS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {lead.nicho && (
          <span className="rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">
            {lead.nicho}
          </span>
        )}

        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Users className="size-3.5" />
          {lead.seguidores ?? 0}
        </span>

        {Boolean(lead.is_private) && (
          <span className="text-xs text-destructive">Perfil privado</span>
        )}
      </div>

      <TagChips tags={lead.tags} />

      {lead.sugestao_dm && (
        <div
          className="flex flex-col gap-2 rounded-lg bg-accent/40 p-3"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="whitespace-pre-line text-sm">{lead.sugestao_dm}</p>
          <Button
            size="sm"
            variant="outline"
            className="w-fit"
            onClick={() => copiar(lead.sugestao_dm ?? "")}
          >
            <Copy className="size-4" />
            {copiado ? "Copiado!" : "Copiar sugestão de DM"}
          </Button>
        </div>
      )}

      {(lead.biography || lead.comentarios.length > 0 || lead.justificativa) && (
        <details
          className="text-xs text-muted-foreground"
          onClick={(e) => e.stopPropagation()}
        >
          <summary className="cursor-pointer select-none hover:text-foreground">
            Bio, comentários e detalhes da análise
          </summary>
          <div className="mt-2 flex flex-col gap-2">
            {lead.biography && (
              <p className="whitespace-pre-line">{lead.biography}</p>
            )}
            {lead.comentarios.length > 0 && (
              <div className="rounded-md bg-muted/40 p-2">
                {lead.comentarios.map((comentario, i) => (
                  <p key={i} className="whitespace-pre-line">
                    "{comentario}"
                  </p>
                ))}
              </div>
            )}
            {lead.justificativa && (
              <p className="italic">{lead.justificativa}</p>
            )}
          </div>
        </details>
      )}

      {lead.lead_dificil && (
        <Button
          size="sm"
          variant="outline"
          className="w-fit border-destructive/40 text-destructive hover:bg-destructive/10"
          onClick={(e) => {
            e.stopPropagation()
            ignorar.mutate(lead.status)
          }}
        >
          <Archive className="size-3.5" />
          Arquivar lead difícil
        </Button>
      )}
    </motion.div>
  )
}
