import { AlertTriangle, Check, Copy, FileText, NotebookPen, Sparkles, Target } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useClipboard } from "@/hooks/useClipboard"
import { cn } from "@/lib/utils"
import {
  COR_ESTAGIO,
  LABEL_ESTAGIO,
  type AnaliseConversa,
  type PropostaComercial,
} from "@/types/conversa"

interface AnaliseConversaCardProps {
  analise: AnaliseConversa | null
  proposta?: PropostaComercial | null
  analisando: boolean
  gerandoProposta?: boolean
  salvandoFicha?: boolean
  temMensagens: boolean
  onAnalisar: () => void
  onGerarProposta?: () => void
  onSalvarFicha?: (resumo: string) => void
  onUsarResposta: (texto: string) => void
}

export function AnaliseConversaCard({
  analise,
  proposta,
  analisando,
  gerandoProposta = false,
  salvandoFicha = false,
  temMensagens,
  onAnalisar,
  onGerarProposta,
  onSalvarFicha,
  onUsarResposta,
}: AnaliseConversaCardProps) {
  const { copiado, copiar } = useClipboard()

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div>
        <h2 className="flex items-center gap-2 font-semibold">
          <Sparkles className="size-4 text-success" />
          Copiloto & CPQ da Negociação
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          A IA lê a conversa, estima a chance de fechar, atualiza a ficha e gera propostas sob medida.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Button onClick={onAnalisar} disabled={analisando || !temMensagens} className="w-full">
          <Sparkles className="size-4" />
          {analisando ? "Analisando..." : "Analisar conversa"}
        </Button>
        {onGerarProposta && (
          <Button
            variant="outline"
            onClick={onGerarProposta}
            disabled={gerandoProposta}
            className="w-full"
          >
            <FileText className="size-4" />
            {gerandoProposta ? "Gerando CPQ..." : "Gerar proposta IA"}
          </Button>
        )}
      </div>

      {!temMensagens && (
        <p className="text-xs text-muted-foreground">
          Registre ao menos uma mensagem para a IA analisar a conversa (ou gere uma proposta direto pelo perfil).
        </p>
      )}

      {proposta && (
        <div className="space-y-3 rounded-xl bg-primary/5 p-3.5">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-primary">
              <FileText className="size-3.5" />
              Proposta CPQ: {proposta.pacote_recomendado}
            </span>
            {proposta.prazo_entrega && (
              <span className="rounded-full bg-background px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                {proposta.prazo_entrega}
              </span>
            )}
          </div>

          {proposta.valor_proposto && (
            <p className="text-sm font-semibold text-foreground">{proposta.valor_proposto}</p>
          )}

          {proposta.itens_inclusos.length > 0 && (
            <ul className="space-y-1 text-xs text-muted-foreground">
              {proposta.itens_inclusos.map((item) => (
                <li key={item} className="flex items-start gap-1.5">
                  <Check className="mt-0.5 size-3.5 shrink-0 text-success" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap gap-2 pt-1">
            {proposta.mensagem_whatsapp && (
              <Button
                size="sm"
                className="flex-1"
                onClick={() => onUsarResposta(proposta.mensagem_whatsapp)}
              >
                Usar resumo no WhatsApp
              </Button>
            )}
            {proposta.documento_proposta && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => copiar(proposta.documento_proposta)}
              >
                <Copy className="size-3.5" />
                {copiado ? "Copiada!" : "Copiar proposta"}
              </Button>
            )}
          </div>
        </div>
      )}

      {analise && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                COR_ESTAGIO[analise.estagio]
              )}
            >
              {LABEL_ESTAGIO[analise.estagio]}
            </span>
            {typeof analise.chance_fechamento === "number" && (
              <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
                {analise.chance_fechamento}% chance de fechar
              </span>
            )}
            {analise.mensagens_consideradas ? (
              <span className="text-[11px] text-muted-foreground">
                com base em {analise.mensagens_consideradas} mensagem(ns)
              </span>
            ) : null}
          </div>

          {analise.leitura && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Leitura
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed">{analise.leitura}</p>
            </div>
          )}

          {analise.resumo_ficha && (
            <div className="rounded-lg bg-muted/40 p-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <NotebookPen className="size-3.5" />
                  Registro automático da ficha
                </h3>
                {onSalvarFicha && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2.5 text-xs"
                    disabled={salvandoFicha}
                    onClick={() => onSalvarFicha(analise.resumo_ficha!)}
                  >
                    {salvandoFicha ? "Salvando..." : "Salvar na ficha"}
                  </Button>
                )}
              </div>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {analise.resumo_ficha}
              </p>
            </div>
          )}

          {analise.objetivo && (
            <div className="rounded-lg border-l-2 border-info bg-info/5 p-3">
              <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-info">
                <Target className="size-3.5" />
                Próximo objetivo
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed">{analise.objetivo}</p>
            </div>
          )}

          {analise.resposta_sugerida && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Resposta sugerida
              </h3>
              <p className="mt-1.5 whitespace-pre-wrap rounded-lg bg-muted/50 p-3 text-sm leading-relaxed">
                {analise.resposta_sugerida}
              </p>
              <Button
                size="sm"
                variant="outline"
                className="mt-2 w-full"
                onClick={() => onUsarResposta(analise.resposta_sugerida)}
              >
                Usar no campo de mensagem
              </Button>
            </div>
          )}

          {analise.evitar.length > 0 && (
            <div>
              <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-warning">
                <AlertTriangle className="size-3.5" />
                Evite agora
              </h3>
              <ul className="mt-1.5 space-y-1">
                {analise.evitar.map((item) => (
                  <li key={item} className="flex gap-2 text-sm text-muted-foreground">
                    <span className="text-warning">•</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
