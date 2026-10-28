import { Link } from "react-router-dom"
import { MessageCircle, MessagesSquare } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useWhatsappConectado } from "@/hooks/useEnvio"
import { linkWhatsappComMensagem } from "@/services/tarefasService"

interface BotaoWhatsappLeadProps {
  placeId: string
  whatsappLink: string
  mensagem?: string | null
  title?: string
}

/** Com a Evolution API conectada, abre a conversa dentro do app; senão, abre
 * o WhatsApp Web por fora com a mensagem preenchida (comportamento original). */
export function BotaoWhatsappLead({ placeId, whatsappLink, mensagem, title }: BotaoWhatsappLeadProps) {
  const conectado = useWhatsappConectado()

  if (conectado) {
    return (
      <Button size="sm" variant="outline" className="h-8 text-xs" asChild>
        <Link to={`/conversas/${encodeURIComponent(placeId)}`}>
          <MessagesSquare className="size-3.5" />
          Abrir conversa
        </Link>
      </Button>
    )
  }

  return (
    <Button size="sm" variant="outline" className="h-8 text-xs" asChild>
      <a href={linkWhatsappComMensagem(whatsappLink, mensagem)} target="_blank" rel="noreferrer" title={title}>
        <MessageCircle className="size-3.5" />
        Abrir WhatsApp
      </a>
    </Button>
  )
}
