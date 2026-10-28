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
from datetime import datetime, timedelta

import db
import mensageiros
from constantes import MAX_CARACTERES_MENSAGEM_CONVERSA
from rotas_conversa import _inserir_mensagem, _variantes_telefone

logger = logging.getLogger(__name__)

INTERVALO_SINCRONIZACAO_SEGUNDOS = 45
# só avisa de mensagens recentes - a primeira sincronização importa o histórico
# antigo e não pode virar uma enxurrada de notificações
JANELA_AVISO_MINUTOS = 30
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


# Frases de mensagem automática de WhatsApp Business (comparadas sem acento e
# em minúsculas). FORTES bastam sozinhas; FRACAS só valem se a mensagem chegou
# logo depois da nossa (robô responde em segundos, pessoa demora mais).
FRASES_AUTOMATICAS_FORTES = (
    "seja bem-vind", "seja muito bem-vind", "bem-vindo(a)", "bem-vinda(o)",
    "estamos ausentes", "estou ausente", "no momento estamos", "nao estou disponivel",
    "nao estamos disponiveis", "responderemos", "retornaremos", "retornarei",
    "agradece seu contato", "agradece o seu contato", "agradecemos seu contato", "agradeco sua mensagem",
    "agradecemos sua mensagem", "obrigado por escolher", "obrigada por escolher", "digite ",
    "responda com o numero", "mensagem automatica", "resposta automatica",
    "horario de atendimento", "nosso horario", "1️⃣", "aguarde nosso retorno",
    "assim que possivel", "assim que retornarmos", "em breve retornaremos",
    "voce entrou em contato", "atendente ja foi notificado", "iniciara o atendimento",
    "nosso whatsapp funciona", "em instantes",
)
FRASES_AUTOMATICAS_FRACAS = (
    "em que podemos ajudar", "como podemos ajudar", "para agilizar", "para facilitar",
    "nome completo", "somos da", "somos a", "aqui e a", "aqui e o",
)
SEGUNDOS_MAX_RESPOSTA_ROBO = 90
# texto longo em poucos segundos: ninguém lê a nossa mensagem e digita isso tão rápido
SEGUNDOS_RESPOSTA_INSTANTANEA = 15
CARACTERES_TEXTO_LONGO = 60


def _normalizar(texto):
    import unicodedata
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    # emojis de número (1️⃣) somem no ascii; confere no texto original também
    return sem_acento.lower(), (texto or "").lower()


def segundos_desde_minha_ultima(minhas_em, enviada_em):
    """Segundos entre a última mensagem nossa ANTES desta e esta (None se não houver)."""
    anteriores = [m for m in minhas_em if m <= enviada_em]
    if not anteriores:
        return None
    try:
        return (datetime.fromisoformat(enviada_em) - datetime.fromisoformat(max(anteriores))).total_seconds()
    except ValueError:
        return None


def e_resposta_automatica(texto, segundos_desde_nossa=None):
    """Mensagem de boas-vindas/menu/ausência do WhatsApp Business do negócio -
    não é uma pessoa respondendo. Ajustado com as conversas reais de 28/10."""
    normalizado, original = _normalizar(texto)
    if any(frase in normalizado or frase in original for frase in FRASES_AUTOMATICAS_FORTES):
        return True
    if (segundos_desde_nossa is not None and segundos_desde_nossa <= SEGUNDOS_RESPOSTA_INSTANTANEA
            and len((texto or "").strip()) >= CARACTERES_TEXTO_LONGO):
        return True
    rapida = segundos_desde_nossa is not None and segundos_desde_nossa <= SEGUNDOS_MAX_RESPOSTA_ROBO
    return rapida and any(frase in normalizado for frase in FRASES_AUTOMATICAS_FRACAS)


def jids_do_lead(lead):
    jids = {f"55{v}@s.whatsapp.net" for v in _variantes_telefone(lead.get("telefone"))}
    if lead.get("whatsapp_jid"):
        jids.add(lead["whatsapp_jid"])
    return jids


def consultas_do_lead(lead):
    """(jid, campo) a consultar na Evolution. Cada número de telefone é buscado
    em remoteJid (conversa endereçada pelo número) E em remoteJidAlt (conversa
    endereçada por @lid, que é como o WhatsApp entrega boa parte das respostas
    desde 2026). O @lid já aprendido do lead também é consultado direto."""
    consultas = []
    for jid in sorted(jids_do_lead(lead)):
        consultas.append((jid, "remoteJid"))
        if jid.endswith("@s.whatsapp.net"):
            consultas.append((jid, "remoteJidAlt"))
    return consultas


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
    novas_minhas = 0
    ultima_do_lead = None  # (enviada_em, texto) da mensagem nova mais recente do lead
    vistos = set()

    jid_lid_descoberto = None
    registros = []
    for jid, campo in consultas_do_lead(lead):
        for registro in mensageiros.buscar_mensagens(jid, MENSAGENS_POR_CONVERSA, campo=campo):
            chave = registro.get("key") or {}
            id_msg = chave.get("id")
            if not id_msg or id_msg in vistos:
                continue
            vistos.add(id_msg)
            if str(chave.get("remoteJid", "")).endswith("@lid"):
                jid_lid_descoberto = chave["remoteJid"]
            registros.append(registro)

    # ordem cronológica: pra saber quanto tempo cada resposta levou desde a
    # nossa última mensagem (resposta automática chega em segundos)
    registros.sort(key=_data_iso)
    minhas_em = [linha[0] for linha in conexao.execute(
        "SELECT enviada_em FROM mensagens_conversa WHERE canal = 'maps' AND lead_ref = ? AND autor = 'vendedor'",
        (place_id,))]
    for registro in registros:
        chave = registro.get("key") or {}
        texto = texto_da_mensagem(registro)
        if not texto:
            continue
        enviada_em = _data_iso(registro)
        autor = "vendedor" if chave.get("fromMe") else "lead"
        automatica = autor == "lead" and e_resposta_automatica(
            texto, segundos_desde_minha_ultima(minhas_em, enviada_em))
        if autor == "vendedor":
            minhas_em.append(enviada_em)
        if _inserir_mensagem(conexao, "maps", place_id, autor,
                             texto[:MAX_CARACTERES_MENSAGEM_CONVERSA],
                             enviada_em, "whatsapp", f"wa:{chave.get('id')}", automatica=automatica):
            novas += 1
            if autor == "vendedor":
                novas_minhas += 1
            elif not automatica:  # só resposta de uma pessoa conta
                novas_do_lead += 1
                if ultima_do_lead is None or enviada_em > ultima_do_lead[0]:
                    ultima_do_lead = (enviada_em, texto)

    # guarda o @lid aprendido: as próximas consultas já vão direto nele
    if jid_lid_descoberto and lead.get("whatsapp_jid") != jid_lid_descoberto:
        conexao.execute("UPDATE leads SET whatsapp_jid = ? WHERE place_id = ?", (jid_lid_descoberto, place_id))

    # mensagem sua que não veio do app = você respondeu pelo celular: o piloto
    # automático sai da conversa (as do app têm a mesma chave e não entram aqui)
    if novas_minhas and lead.get("piloto_status") == "automatico":
        conexao.execute("UPDATE leads SET piloto_status = 'humano' WHERE place_id = ?", (place_id,))

    # lead que está com você (não com o piloto) respondeu agora: avisa
    if ultima_do_lead and lead.get("piloto_status") != "automatico":
        limite = (datetime.now() - timedelta(minutes=JANELA_AVISO_MINUTOS)).isoformat(timespec="seconds")
        if ultima_do_lead[0] >= limite:
            nome = lead.get("nome") or "Um lead"
            mensageiros.avisar_vendedor(f"💬 {nome} respondeu no WhatsApp:\n“{ultima_do_lead[1][:300]}”")

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
        SELECT place_id, nome, telefone, status, whatsapp_jid, piloto_status FROM leads
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
                # grava lead a lead: nunca segura o banco durante as chamadas à Evolution
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


def reclassificar_respostas_automaticas():
    """Reaplica a detecção de resposta automática no histórico já importado e
    devolve para 'contatado' os leads que só "responderam" com robô (status
    'respondeu' sem nenhuma mensagem de pessoa). Idempotente - roda no startup."""
    conexao = db.conectar()
    try:
        por_lead = {}
        for linha in conexao.execute(
            "SELECT id, lead_ref, autor, texto, enviada_em FROM mensagens_conversa "
            "WHERE canal = 'maps' ORDER BY enviada_em, id"
        ):
            por_lead.setdefault(linha["lead_ref"], []).append(dict(linha))

        for mensagens in por_lead.values():
            minhas_em = []
            for m in mensagens:
                if m["autor"] == "vendedor":
                    minhas_em.append(m["enviada_em"])
                    continue
                automatica = e_resposta_automatica(m["texto"], segundos_desde_minha_ultima(minhas_em, m["enviada_em"]))
                conexao.execute("UPDATE mensagens_conversa SET automatica = ? WHERE id = ?", (int(automatica), m["id"]))

        agora = datetime.now().isoformat(timespec="seconds")
        so_robo = conexao.execute(
            """
            SELECT place_id FROM leads l WHERE status = 'respondeu' AND NOT EXISTS (
                SELECT 1 FROM mensagens_conversa m WHERE m.canal = 'maps' AND m.lead_ref = l.place_id
                  AND m.autor = 'lead' AND m.automatica = 0)
              AND EXISTS (
                SELECT 1 FROM mensagens_conversa m WHERE m.canal = 'maps' AND m.lead_ref = l.place_id
                  AND m.automatica = 1)
            """
        ).fetchall()
        for linha in so_robo:
            conexao.execute("UPDATE leads SET status = 'contatado', atualizado_em = ? WHERE place_id = ?",
                            (agora, linha["place_id"]))
            conexao.execute(
                "INSERT INTO historico_status (place_id, status_anterior, status_novo, alterado_em) "
                "VALUES (?, 'respondeu', 'contatado', ?)", (linha["place_id"], agora))
        conexao.commit()
        if so_robo:
            logger.info("%s lead(s) voltaram para 'contatado': só havia resposta automática", len(so_robo))
        return len(so_robo)
    finally:
        conexao.close()
