"""Traz as conversas do WhatsApp (guardadas pela Evolution API) para o histórico
de cada lead, dentro do ProspectOS.

Como funciona:
- Para cada lead "em conversa", consulta a Evolution pelos JIDs possíveis do
  número (com e sem o 9º dígito) e pelo JID salvo no envio (pode ser @lid).
- Grava no `mensagens_conversa` com origem "whatsapp" e chave_dedup
  "wa:<id da mensagem>" - a mesma chave que o envio pelo app usa, então a
  mensagem enviada pelo ProspectOS não aparece duplicada.
- Mensagem nova do lead move o lead de "novo"/"contatado" para "respondeu".

Roda em segundo plano (thread iniciada pelo app.py) e também sob demanda,
para um lead só, quando a conversa está aberta na tela.
"""

import logging
import threading
from datetime import datetime

import db
import mensageiros
from constantes import MAX_CARACTERES_MENSAGEM_CONVERSA
from rotas_conversa import _inserir_mensagem, _variantes_telefone

logger = logging.getLogger(__name__)

INTERVALO_SINCRONIZACAO_SEGUNDOS = 60
MAX_LEADS_POR_SINCRONIZACAO = 300
MENSAGENS_POR_CONVERSA = 100
STATUS_QUE_VIRAM_RESPONDEU = {"novo", "contatado"}

_estado = {"ultima_em": None, "novas": 0, "erro": None}
_trava = threading.Lock()


def estado_sincronizacao():
    return dict(_estado)


def texto_da_mensagem(registro):
    """Extrai um texto legível de qualquer tipo de mensagem do WhatsApp."""
    msg = registro.get("message") or {}
    if msg.get("conversation"):
        return msg["conversation"]
    if (msg.get("extendedTextMessage") or {}).get("text"):
        return msg["extendedTextMessage"]["text"]

    rotulos = {
        "imageMessage": "📷 Imagem",
        "videoMessage": "🎥 Vídeo",
        "audioMessage": "🎤 Áudio",
        "documentMessage": "📄 Documento",
        "stickerMessage": "Figurinha",
        "locationMessage": "📍 Localização",
        "contactMessage": "👤 Contato",
    }
    for tipo, rotulo in rotulos.items():
        if tipo in msg:
            legenda = (msg[tipo] or {}).get("caption") or (msg[tipo] or {}).get("fileName")
            return f"[{rotulo}]" + (f" {legenda}" if legenda else "")
    tipo = registro.get("messageType") or "mensagem"
    if tipo in ("protocolMessage", "reactionMessage", "senderKeyDistributionMessage"):
        return None  # eventos técnicos, não são conversa
    return f"[{tipo}]"


def jids_do_lead(lead):
    jids = {f"55{v}@s.whatsapp.net" for v in _variantes_telefone(lead.get("telefone"))}
    if lead.get("whatsapp_jid"):
        jids.add(lead["whatsapp_jid"])
    return jids


def _data_iso(registro):
    try:
        return datetime.fromtimestamp(int(registro.get("messageTimestamp"))).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return datetime.now().isoformat(timespec="seconds")


def sincronizar_lead(conexao, lead):
    """Sincroniza um lead do Maps. Retorna quantas mensagens novas gravou.
    Não faz commit - quem chama decide."""
    place_id = lead["place_id"]
    novas = 0
    novas_do_lead = 0
    vistos = set()

    for jid in jids_do_lead(lead):
        for registro in mensageiros.buscar_mensagens(jid, MENSAGENS_POR_CONVERSA):
            chave = registro.get("key") or {}
            id_msg = chave.get("id")
            if not id_msg or id_msg in vistos:
                continue
            vistos.add(id_msg)
            texto = texto_da_mensagem(registro)
            if not texto:
                continue
            autor = "vendedor" if chave.get("fromMe") else "lead"
            if _inserir_mensagem(conexao, "maps", place_id, autor,
                                 texto[:MAX_CARACTERES_MENSAGEM_CONVERSA],
                                 _data_iso(registro), "whatsapp", f"wa:{id_msg}"):
                novas += 1
                if autor == "lead":
                    novas_do_lead += 1

    if novas_do_lead and lead.get("status") in STATUS_QUE_VIRAM_RESPONDEU:
        agora = datetime.now().isoformat(timespec="seconds")
        conexao.execute(
            "UPDATE leads SET status = 'respondeu', atualizado_em = ? WHERE place_id = ?",
            (agora, place_id),
        )
        conexao.execute(
            "INSERT INTO historico_status (place_id, status_anterior, status_novo, alterado_em) "
            "VALUES (?, ?, 'respondeu', ?)",
            (place_id, lead["status"], agora),
        )
        logger.info("lead %s respondeu no WhatsApp - status atualizado", place_id)
    return novas


def leads_em_conversa(conexao):
    """Leads com telefone que já saíram do 'novo' ou já têm mensagem no histórico."""
    linhas = conexao.execute(
        """
        SELECT place_id, telefone, status, whatsapp_jid FROM leads
        WHERE telefone IS NOT NULL AND telefone != '' AND status != 'ignorado'
          AND (status != 'novo' OR place_id IN
               (SELECT lead_ref FROM mensagens_conversa WHERE canal = 'maps'))
        ORDER BY atualizado_em DESC LIMIT ?
        """,
        (MAX_LEADS_POR_SINCRONIZACAO,),
    ).fetchall()
    return [dict(linha) for linha in linhas]


def sincronizar_todos():
    """Uma rodada completa. Retorna o total de mensagens novas."""
    if not _trava.acquire(blocking=False):
        return 0  # já tem uma rodada em andamento
    try:
        conexao = db.conectar()
        try:
            total = 0
            for lead in leads_em_conversa(conexao):
                total += sincronizar_lead(conexao, lead)
            conexao.commit()
        finally:
            conexao.close()
        _estado.update({"ultima_em": datetime.now().isoformat(timespec="seconds"),
                        "novas": total, "erro": None})
        if total:
            logger.info("sincronização do WhatsApp: %s mensagem(ns) nova(s)", total)
        return total
    except mensageiros.ErroEnvio as erro:
        _estado.update({"erro": str(erro)})
        return 0
    finally:
        _trava.release()


def _laco_em_segundo_plano(parar):
    while not parar.wait(INTERVALO_SINCRONIZACAO_SEGUNDOS):
        try:
            if mensageiros.estado_whatsapp() == "open":
                sincronizar_todos()
        except mensageiros.ErroEnvio:
            pass  # WhatsApp não configurado ou Evolution fora do ar: tenta na próxima
        except Exception:
            logger.exception("falha inesperada na sincronização do WhatsApp")


def iniciar_em_segundo_plano():
    parar = threading.Event()
    threading.Thread(target=_laco_em_segundo_plano, args=(parar,), daemon=True,
                     name="sincronizacao-whatsapp").start()
    return parar
