"""Piloto automático: escolhe os melhores leads de uma área, manda a primeira
mensagem pelo WhatsApp e responde às perguntas simples dos leads, passando a
conversa para o vendedor quando precisa de uma pessoa.

Proteções (o número do vendedor é o ativo mais caro aqui):
- só envia dentro da janela de horário (padrão 9h-18h, seg-sex);
- intervalo aleatório entre primeiros contatos (padrão 4-9 min) - ritmo humano;
- respeita o limite diário de envios do WhatsApp (o mesmo do envio manual);
- lead que pede pra parar recebe uma despedida curta e nunca mais é contatado;
- no máximo `piloto_max_respostas` respostas automáticas seguidas por lead;
- preço não informado, fechamento, áudio, irritação ou dúvida -> passa pra você;
- lead quer ver como ficaria -> o piloto combina a prévia para o próximo dia útil,
  cria a tarefa (follow-up + tag "prévia") e passa a conversa pra você montar o site;
- lead que não respondeu recebe follow-ups no D2, D5, D9 e D14 depois do primeiro
  contato (o último é uma despedida) - no mesmo ritmo e limite dos primeiros contatos;
- quem responde é robô de atendimento -> um recado único pedindo o caminho até o dono.

Estado da conversa em `leads.piloto_status`:
  'automatico'   - o piloto conduz (só esses recebem resposta automática)
  'humano'       - você assumiu, ou o piloto combinou a prévia e passou pra você
  'encerrado'    - o lead pediu pra parar
  'sem_whatsapp' - o número não tem WhatsApp
"""

import logging
import random
import threading
import unicodedata
from datetime import datetime, timedelta

import abordagem
import db
import ia
import mensageiros
from rotas_conversa import _listar_mensagens

logger = logging.getLogger(__name__)

INTERVALO_LACO_SEGUNDOS = 20
# espera mínima após a mensagem do lead antes de responder (resposta instantânea soa robô)
ATRASO_MINIMO_RESPOSTA_SEGUNDOS = 45

CONFIG_PADRAO = {
    "piloto_ativo": "0",
    "piloto_auto_resposta": "1",
    "piloto_nicho": "",
    "piloto_cidade": "",
    "piloto_score_min": "0",
    "piloto_hora_inicio": "9",
    "piloto_hora_fim": "18",
    "piloto_fim_de_semana": "0",
    "piloto_intervalo_min": "4",
    "piloto_intervalo_max": "9",
    "piloto_max_respostas": "4",
    "piloto_info_oferta": "",
    "piloto_followup": "1",
    "piloto_recado_robo": "1",
}

DESPEDIDA_OPT_OUT = "Sem problemas, obrigado pelo retorno! Não vou mais te incomodar. Sucesso aí!"

# frases que significam "pare" - tratadas sem IA, na hora, sem risco de insistir
_FRASES_OPT_OUT = (
    "nao tenho interesse", "nao temos interesse", "sem interesse", "nao quero", "nao precisamos",
    "nao preciso", "pare de", "para de mandar", "parar de mandar", "nao me mande", "nao mande mais",
    "me tira", "me remove", "remover meu", "descadastr", "spam", "nao insista", "bloquear",
    # recusas educadas vistas nas conversas reais de 28/10
    "nao obrigad", "nao e viavel", "nao, obrigad", "ja temos site", "ja temos um site",
    "ja estamos com um site", "ja estamos com site", "ja tenho site", "ja tenho um site",
)

_estado = {"proximo_contato_em": None, "ultimo_erro": None, "rodando": False}
_trava = threading.Lock()


# ---------------------------------------------------------------------------
# Configuração e eventos
# ---------------------------------------------------------------------------

def config():
    return {chave: db.obter_config(chave) or padrao for chave, padrao in CONFIG_PADRAO.items()}


def _int(cfg, chave):
    try:
        return int(cfg[chave])
    except (TypeError, ValueError):
        return int(CONFIG_PADRAO[chave])


def registrar_evento(conexao, tipo, place_id=None, nome=None, detalhe=None):
    conexao.execute(
        "INSERT INTO piloto_eventos (em, tipo, place_id, nome, detalhe) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), tipo, place_id, nome, detalhe),
    )


def estado():
    return dict(_estado)


def _avisar(texto):
    """Telegram e/ou WhatsApp do vendedor - o que estiver configurado."""
    mensageiros.avisar_vendedor(texto)


# ---------------------------------------------------------------------------
# Regras de tempo
# ---------------------------------------------------------------------------

def dentro_do_horario(cfg, agora=None):
    agora = agora or datetime.now()
    if agora.weekday() >= 5 and cfg["piloto_fim_de_semana"] != "1":
        return False
    return _int(cfg, "piloto_hora_inicio") <= agora.hour < _int(cfg, "piloto_hora_fim")


def _sortear_proximo_contato(cfg, agora=None):
    minimo = max(1, _int(cfg, "piloto_intervalo_min"))
    maximo = max(minimo, _int(cfg, "piloto_intervalo_max"))
    segundos = random.randint(minimo * 60, maximo * 60)
    return (agora or datetime.now()) + timedelta(seconds=segundos)


# ---------------------------------------------------------------------------
# Escolha dos leads
# ---------------------------------------------------------------------------

def proximos_leads(conexao, cfg, limite=5):
    """Fila do piloto: leads novos da área escolhida, com telefone, que o piloto
    ainda não tocou, do maior score pro menor."""
    from rotas_leads import SQL_SCORE

    condicoes = [
        "status = 'novo'",
        "telefone IS NOT NULL AND telefone != ''",
        "piloto_status IS NULL",
        f"{SQL_SCORE} >= ?",
    ]
    parametros = [_int(cfg, "piloto_score_min")]
    if cfg["piloto_nicho"].strip():
        condicoes.append("LOWER(COALESCE(nicho, '') || ' ' || COALESCE(categoria, '')) LIKE ?")
        parametros.append(f"%{cfg['piloto_nicho'].strip().lower()}%")
    if cfg["piloto_cidade"].strip():
        condicoes.append("LOWER(COALESCE(cidade, '') || ' ' || COALESCE(endereco, '')) LIKE ?")
        parametros.append(f"%{cfg['piloto_cidade'].strip().lower()}%")

    linhas = conexao.execute(
        f"SELECT *, {SQL_SCORE} AS score FROM leads WHERE {' AND '.join(condicoes)} "
        f"ORDER BY score DESC, nota DESC LIMIT ?",
        (*parametros, limite),
    ).fetchall()
    return [dict(linha) for linha in linhas]


# ---------------------------------------------------------------------------
# Primeiro contato
# ---------------------------------------------------------------------------

def fazer_primeiro_contato(cfg):
    """Escolhe o melhor lead da fila, gera a mensagem e envia. Retorna o nome do
    lead contatado ou None se não havia ninguém na fila."""
    from rotas_envio import _enviados_hoje, _limite_diario, enviar_e_registrar
    from rotas_leads import gerar_copy_para_lead

    conexao = db.conectar()
    try:
        if _enviados_hoje(conexao) >= _limite_diario():
            return None
        fila = proximos_leads(conexao, cfg, limite=1)
        if not fila:
            return None
        lead = fila[0]
        # reserva o lead antes de chamar IA/rede: se algo falhar no meio, ele não
        # é escolhido de novo na próxima volta
        conexao.execute("UPDATE leads SET piloto_status = 'automatico', piloto_respostas = 0 "
                        "WHERE place_id = ?", (lead["place_id"],))
        conexao.commit()

        mensagem = lead.get("mensagem_gerada")
        if not mensagem:
            try:
                mensagem, _provedor, _avisos = gerar_copy_para_lead(conexao, lead, "contato")
            except Exception as erro:
                # IA indisponível: devolve o lead pra fila e tenta na próxima volta
                conexao.execute("UPDATE leads SET piloto_status = NULL WHERE place_id = ?",
                                (lead["place_id"],))
                registrar_evento(conexao, "erro", lead["place_id"], lead["nome"],
                                 f"Não consegui gerar a mensagem: {erro}")
                conexao.commit()
                raise
    finally:
        conexao.close()

    texto = ia.ajustar_saudacao(mensagem)

    try:
        enviar_e_registrar("maps", lead["place_id"], lead, texto)
    except mensageiros.ErroEnvio as erro:
        conexao = db.conectar()
        try:
            sem_whatsapp = "não tem WhatsApp" in str(erro)
            if sem_whatsapp:
                conexao.execute("UPDATE leads SET piloto_status = 'sem_whatsapp' WHERE place_id = ?",
                                (lead["place_id"],))
            else:
                # falha passageira (Evolution fora, rede): devolve o lead pra fila
                conexao.execute("UPDATE leads SET piloto_status = NULL WHERE place_id = ?",
                                (lead["place_id"],))
            registrar_evento(conexao, "sem_whatsapp" if sem_whatsapp else "erro",
                             lead["place_id"], lead["nome"], str(erro))
            conexao.commit()
        finally:
            conexao.close()
        if not sem_whatsapp:
            raise
        return None

    conexao = db.conectar()
    try:
        registrar_evento(conexao, "contato_enviado", lead["place_id"], lead["nome"], texto)
        conexao.commit()
    finally:
        conexao.close()
    return lead["nome"]


# ---------------------------------------------------------------------------
# Follow-up de quem não respondeu
# ---------------------------------------------------------------------------

def _data(texto_iso):
    return datetime.fromisoformat(str(texto_iso)[:19])


def leads_para_followup(conexao, agora=None):
    """Leads do piloto que nunca responderam (robô não conta) e cujo próximo
    follow-up da cadência já venceu, do mais atrasado pro mais recente. Nunca
    dois envios no mesmo dia pro mesmo lead."""
    agora = agora or datetime.now()
    linhas = conexao.execute(
        """
        SELECT l.*,
               (SELECT MIN(enviada_em) FROM mensagens_conversa
                 WHERE canal = 'maps' AND lead_ref = l.place_id AND autor = 'vendedor') AS primeiro_envio_em,
               (SELECT MAX(enviada_em) FROM mensagens_conversa
                 WHERE canal = 'maps' AND lead_ref = l.place_id AND autor = 'vendedor') AS ultimo_envio_em
        FROM leads l
        WHERE l.piloto_status = 'automatico' AND l.status = 'contatado'
          AND COALESCE(l.follow_ups_enviados, 0) < ?
          AND NOT EXISTS (SELECT 1 FROM mensagens_conversa
                           WHERE canal = 'maps' AND lead_ref = l.place_id AND autor = 'lead' AND automatica = 0)
        """,
        (len(abordagem.CADENCIA_FOLLOWUP_DIAS),),
    ).fetchall()

    vencidos = []
    for linha in linhas:
        lead = dict(linha)
        if not lead["primeiro_envio_em"]:
            continue
        dias = abordagem.CADENCIA_FOLLOWUP_DIAS[lead["follow_ups_enviados"] or 0]
        vence_em = _data(lead["primeiro_envio_em"]).date() + timedelta(days=dias)
        if agora.date() >= vence_em and _data(lead["ultimo_envio_em"]).date() < agora.date():
            lead["vence_em"] = vence_em
            vencidos.append(lead)
    vencidos.sort(key=lambda l: l["vence_em"])
    return vencidos


def fazer_followup(cfg, agora=None):
    """Manda o follow-up mais atrasado da cadência. Retorna o nome do lead, ou
    None se não havia nenhum vencido (ou se o limite do dia acabou)."""
    from rotas_envio import _enviados_hoje, _limite_diario, enviar_e_registrar
    from rotas_leads import gerar_copy_para_lead

    conexao = db.conectar()
    try:
        if _enviados_hoje(conexao) >= _limite_diario():
            return None
        vencidos = leads_para_followup(conexao, agora)
        if not vencidos:
            return None
        lead = vencidos[0]
        ja_enviado = "\n---\n".join(
            m["texto"] for m in _listar_mensagens(conexao, "maps", lead["place_id"]) if m["autor"] == "vendedor")
        try:
            mensagem, _provedor, _avisos = gerar_copy_para_lead(
                conexao, lead, "followup", mensagens_anteriores=ja_enviado)
        except Exception as erro:
            # IA fora: este horário vai pra um primeiro contato; o follow-up tenta de novo depois
            registrar_evento(conexao, "erro", lead["place_id"], lead["nome"],
                             f"Não consegui gerar o follow-up: {erro}")
            conexao.commit()
            return None
    finally:
        conexao.close()

    texto = ia.ajustar_saudacao(mensagem)
    enviar_e_registrar("maps", lead["place_id"], lead, texto)

    numero = (lead["follow_ups_enviados"] or 0) + 1
    ultimo = numero >= len(abordagem.CADENCIA_FOLLOWUP_DIAS)
    agora_iso = datetime.now().isoformat(timespec="seconds")
    conexao = db.conectar()
    try:
        conexao.execute(
            "UPDATE leads SET follow_ups_enviados = ?, ultimo_followup_em = ?, atualizado_em = ? "
            "WHERE place_id = ?", (numero, agora_iso, agora_iso, lead["place_id"]))
        registrar_evento(conexao, "followup_enviado", lead["place_id"], lead["nome"],
                         f"{numero}º follow-up{' (despedida)' if ultimo else ''}: {texto}")
        conexao.commit()
    finally:
        conexao.close()
    return lead["nome"]


# ---------------------------------------------------------------------------
# Robô de atendimento
# ---------------------------------------------------------------------------

def leads_com_robo(conexao, agora=None):
    """Leads do piloto em que só um robô respondeu (a última mensagem é uma
    resposta automática) e que ainda não receberam o recado pro dono."""
    limite = ((agora or datetime.now()) - timedelta(seconds=ATRASO_MINIMO_RESPOSTA_SEGUNDOS)
              ).isoformat(timespec="seconds")
    linhas = conexao.execute(
        """
        SELECT l.* FROM leads l
        JOIN mensagens_conversa m ON m.id = (
            SELECT id FROM mensagens_conversa
            WHERE canal = 'maps' AND lead_ref = l.place_id
            ORDER BY enviada_em DESC, id DESC LIMIT 1)
        WHERE l.piloto_status = 'automatico' AND l.status = 'contatado'
          AND m.autor = 'lead' AND m.automatica = 1 AND m.enviada_em <= ?
          AND NOT EXISTS (SELECT 1 FROM piloto_eventos e
                           WHERE e.place_id = l.place_id AND e.tipo = 'recado_robo')
        """,
        (limite,),
    ).fetchall()
    return [dict(linha) for linha in linhas]


def mandar_recado_robo(lead):
    """Recado único pra quem respondeu com robô: não sou cliente, qual o
    caminho até o dono? Escrito sem IA (abordagem.RECADOS_PARA_ROBO)."""
    from rotas_envio import _enviados_hoje, _limite_diario, enviar_e_registrar

    conexao = db.conectar()
    try:
        if _enviados_hoje(conexao) >= _limite_diario():
            return False
    finally:
        conexao.close()

    texto = abordagem.recado_para_robo(ia.nome_curto_empresa(lead["nome"]))
    enviar_e_registrar("maps", lead["place_id"], lead, texto)
    conexao = db.conectar()
    try:
        registrar_evento(conexao, "recado_robo", lead["place_id"], lead["nome"], texto)
        conexao.commit()
    finally:
        conexao.close()
    return True


# ---------------------------------------------------------------------------
# Respostas automáticas
# ---------------------------------------------------------------------------

def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def e_opt_out(texto):
    normalizado = _normalizar(texto)
    return any(frase in normalizado for frase in _FRASES_OPT_OUT)


def leads_aguardando_resposta(conexao, agora=None):
    """Leads conduzidos pelo piloto cuja última mensagem é do lead e já tem
    pelo menos ATRASO_MINIMO_RESPOSTA_SEGUNDOS."""
    limite = ((agora or datetime.now()) - timedelta(seconds=ATRASO_MINIMO_RESPOSTA_SEGUNDOS)
              ).isoformat(timespec="seconds")
    linhas = conexao.execute(
        """
        SELECT l.* FROM leads l
        JOIN mensagens_conversa m ON m.id = (
            SELECT id FROM mensagens_conversa
            WHERE canal = 'maps' AND lead_ref = l.place_id AND automatica = 0
            ORDER BY enviada_em DESC, id DESC LIMIT 1)
        WHERE l.piloto_status = 'automatico' AND m.autor = 'lead' AND m.enviada_em <= ?
        """,
        (limite,),
    ).fetchall()
    return [dict(linha) for linha in linhas]


def _passar_para_humano(conexao, lead, motivo):
    conexao.execute("UPDATE leads SET piloto_status = 'humano' WHERE place_id = ?", (lead["place_id"],))
    registrar_evento(conexao, "passou_para_voce", lead["place_id"], lead["nome"], motivo)
    conexao.commit()
    _avisar(f"🙋 {lead['nome']} precisa de você no WhatsApp.\nMotivo: {motivo}")


def combinar_previa(conexao, lead, resposta):
    """Prévia combinada: vira tarefa do vendedor para o próximo dia útil e a
    conversa sai do piloto (quem envia a prévia e negocia é você)."""
    data_entrega, falado = ia.proximo_dia_util()
    tags = [t.strip() for t in (lead.get("tags") or "").split(",") if t.strip()]
    if "prévia" not in tags:
        tags.append("prévia")
    conexao.execute(
        "UPDATE leads SET piloto_status = 'humano', tags = ?, proximo_followup = ?, atualizado_em = ? "
        "WHERE place_id = ?",
        (", ".join(tags), data_entrega.isoformat(), datetime.now().isoformat(timespec="seconds"),
         lead["place_id"]),
    )
    registrar_evento(conexao, "previa_combinada", lead["place_id"], lead["nome"],
                     f"Entregar {falado} ({data_entrega.strftime('%d/%m')}). Mensagem: {resposta}")
    _avisar(f"🎨 Prévia combinada com {lead['nome']} para {falado} "
                     f"({data_entrega.strftime('%d/%m')}). Bora montar o site!")


def responder_lead(lead, cfg):
    """Decide e executa a resposta para um lead. Retorna a ação tomada."""
    from rotas_envio import enviar_e_registrar

    conexao = db.conectar()
    try:
        mensagens = _listar_mensagens(conexao, "maps", lead["place_id"])
        ultima = mensagens[-1]["texto"] if mensagens else ""

        if e_opt_out(ultima):
            decisao = {"acao": "encerrar", "motivo": "O lead pediu para parar.",
                       "resposta": DESPEDIDA_OPT_OUT}
        elif (lead.get("piloto_respostas") or 0) >= _int(cfg, "piloto_max_respostas"):
            _passar_para_humano(conexao, lead, "Limite de respostas automáticas seguidas atingido.")
            return "passar_para_humano"
        else:
            decisao, _provedor, _avisos = ia.decidir_resposta_piloto(
                lead, mensagens, cfg["piloto_info_oferta"])

        if decisao["acao"] == "passar_para_humano":
            _passar_para_humano(conexao, lead, decisao["motivo"] or "A IA preferiu não responder sozinha.")
            return "passar_para_humano"
    finally:
        conexao.close()

    enviar_e_registrar("maps", lead["place_id"], lead, decisao["resposta"])

    conexao = db.conectar()
    try:
        if decisao["acao"] == "combinar_previa":
            combinar_previa(conexao, lead, decisao["resposta"])
        elif decisao["acao"] == "encerrar":
            agora = datetime.now().isoformat(timespec="seconds")
            conexao.execute(
                "UPDATE leads SET piloto_status = 'encerrado', status = 'recusou', proximo_followup = NULL, "
                "atualizado_em = ? WHERE place_id = ?", (agora, lead["place_id"]))
            conexao.execute(
                "INSERT INTO historico_status (place_id, status_anterior, status_novo, alterado_em) "
                "VALUES (?, ?, 'recusou', ?)", (lead["place_id"], lead["status"], agora))
            registrar_evento(conexao, "encerrado", lead["place_id"], lead["nome"],
                             decisao["motivo"] or "O lead não tem interesse.")
        else:
            conexao.execute("UPDATE leads SET piloto_respostas = piloto_respostas + 1 WHERE place_id = ?",
                            (lead["place_id"],))
            registrar_evento(conexao, "resposta_enviada", lead["place_id"], lead["nome"], decisao["resposta"])
        conexao.commit()
    finally:
        conexao.close()
    return decisao["acao"]


# ---------------------------------------------------------------------------
# Laço
# ---------------------------------------------------------------------------

def rodar_uma_vez(agora=None):
    """Uma volta do piloto. Separado do laço pra ser testável."""
    cfg = config()
    agora = agora or datetime.now()
    if not dentro_do_horario(cfg, agora):
        return
    if mensageiros.estado_whatsapp() != "open":
        return

    if cfg["piloto_auto_resposta"] == "1" or cfg["piloto_recado_robo"] == "1":
        import sincronizacao_whatsapp
        sincronizacao_whatsapp.sincronizar_todos()
        conexao = db.conectar()
        try:
            pendentes = leads_aguardando_resposta(conexao, agora) if cfg["piloto_auto_resposta"] == "1" else []
            com_robo = leads_com_robo(conexao, agora) if cfg["piloto_recado_robo"] == "1" else []
        finally:
            conexao.close()
        for lead in com_robo:
            if not mandar_recado_robo(lead):
                break  # limite do dia
        for lead in pendentes:
            try:
                responder_lead(lead, cfg)
            except Exception as erro:
                logger.exception("piloto: falha ao responder %s", lead["place_id"])
                conexao = db.conectar()
                try:
                    _passar_para_humano(conexao, lead, f"Não consegui responder sozinho ({erro}).")
                finally:
                    conexao.close()

    if cfg["piloto_ativo"] == "1":
        proximo = _estado["proximo_contato_em"]
        if proximo is None or agora >= datetime.fromisoformat(proximo):
            # follow-up vencido tem prioridade: é nele que a maioria das vendas acontece
            if not (cfg["piloto_followup"] == "1" and fazer_followup(cfg, agora)):
                fazer_primeiro_contato(cfg)
            _estado["proximo_contato_em"] = _sortear_proximo_contato(cfg, agora).isoformat(timespec="seconds")


def _laco(parar):
    while not parar.wait(INTERVALO_LACO_SEGUNDOS):
        if not _trava.acquire(blocking=False):
            continue
        try:
            _estado["rodando"] = True
            rodar_uma_vez()
            _estado["ultimo_erro"] = None
        except mensageiros.ErroEnvio as erro:
            _estado["ultimo_erro"] = str(erro)
        except Exception as erro:
            logger.exception("falha inesperada no piloto automático")
            _estado["ultimo_erro"] = str(erro)
        finally:
            _estado["rodando"] = False
            _trava.release()


def iniciar_em_segundo_plano():
    parar = threading.Event()
    threading.Thread(target=_laco, args=(parar,), daemon=True, name="piloto-automatico").start()
    return parar
