"""Rotas de envio direto: WhatsApp (Evolution API) e Telegram (bot), mais a
escolha do modelo do Gemini.

Regras de negócio do envio pelo WhatsApp:
- Sempre um lead por vez, disparado por clique do usuário - não existe envio
  em massa. É a principal proteção contra banimento do número.
- Limite diário configurável (padrão LIMITE_DIARIO_WHATSAPP_PADRAO), contado
  pelas mensagens com origem "app" gravadas hoje no histórico.
- Toda mensagem enviada entra no histórico do cockpit (origem "app") e um lead
  do Maps em "novo" passa pra "contatado", com registro no histórico de status.
"""

import logging
from datetime import date, datetime

from flask import Blueprint, jsonify, request

import db
import ia
import mensageiros
from constantes import MAX_CARACTERES_MENSAGEM_CONVERSA, STATUS_QUE_ENCERRAM_FOLLOWUP
from rotas_config import mascarar_chave
from rotas_conversa import _inserir_mensagem, _validar_alvo

logger = logging.getLogger(__name__)

bp = Blueprint("envio", __name__)

LIMITE_DIARIO_WHATSAPP_PADRAO = 30
LIMITE_DIARIO_WHATSAPP_MAXIMO = 200
EVOLUTION_URL_PADRAO = "http://localhost:8080"
EVOLUTION_INSTANCIA_PADRAO = "prospectos"


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _limite_diario():
    try:
        return int(db.obter_config("whatsapp_limite_diario") or LIMITE_DIARIO_WHATSAPP_PADRAO)
    except ValueError:
        return LIMITE_DIARIO_WHATSAPP_PADRAO


def _enviados_hoje(conexao):
    return conexao.execute(
        "SELECT COUNT(*) FROM mensagens_conversa WHERE origem = 'app' AND autor = 'vendedor' "
        "AND substr(enviada_em, 1, 10) = ?",
        (date.today().isoformat(),),
    ).fetchone()[0]


def _erro(excecao, status=400):
    return jsonify({"erro": str(excecao)}), status


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

@bp.route("/api/envio/config")
def obter_config_envio():
    conexao = db.conectar()
    try:
        enviados = _enviados_hoje(conexao)
    finally:
        conexao.close()

    chave_evolution = db.obter_config("evolution_api_key")
    token_telegram = db.obter_config("telegram_bot_token")
    return jsonify({
        "whatsapp": {
            "url": db.obter_config("evolution_url") or EVOLUTION_URL_PADRAO,
            "instancia": db.obter_config("evolution_instancia") or EVOLUTION_INSTANCIA_PADRAO,
            "chave_configurada": bool(chave_evolution),
            "chave_mascarada": mascarar_chave(chave_evolution),
            "limite_diario": _limite_diario(),
            "enviados_hoje": enviados,
        },
        "telegram": {
            "token_configurado": bool(token_telegram),
            "token_mascarado": mascarar_chave(token_telegram),
            "chat_id": db.obter_config("telegram_chat_id") or "",
        },
        "gemini": {
            "modelo": ia.modelo_gemini(),
            "opcoes": [{"valor": v, "rotulo": r} for v, r in ia.MODELOS_GEMINI.items()],
        },
    })


@bp.route("/api/envio/config/whatsapp", methods=["POST"])
def salvar_config_whatsapp():
    dados = request.json or {}
    url = str(dados.get("url", "")).strip().rstrip("/")
    instancia = str(dados.get("instancia", "")).strip()
    chave = str(dados.get("chave", "")).strip()

    if not url.startswith(("http://", "https://")):
        return jsonify({"erro": "a URL da Evolution API deve começar com http:// ou https://"}), 400
    if not instancia or not instancia.replace("-", "").replace("_", "").isalnum():
        return jsonify({"erro": "nome da instância inválido (use letras, números, - ou _)"}), 400
    try:
        limite = int(dados.get("limite_diario", LIMITE_DIARIO_WHATSAPP_PADRAO))
    except (TypeError, ValueError):
        return jsonify({"erro": "limite diário deve ser um número"}), 400
    if not 1 <= limite <= LIMITE_DIARIO_WHATSAPP_MAXIMO:
        return jsonify({"erro": f"limite diário deve ficar entre 1 e {LIMITE_DIARIO_WHATSAPP_MAXIMO}"}), 400

    db.salvar_config("evolution_url", url)
    db.salvar_config("evolution_instancia", instancia)
    db.salvar_config("whatsapp_limite_diario", str(limite))
    if chave:
        db.salvar_config("evolution_api_key", chave)
    return jsonify({"ok": True})


@bp.route("/api/envio/config/telegram", methods=["POST"])
def salvar_config_telegram():
    dados = request.json or {}
    token = str(dados.get("token", "")).strip()
    chat_id = str(dados.get("chat_id", "")).strip()
    if token:
        db.salvar_config("telegram_bot_token", token)
    if chat_id:
        db.salvar_config("telegram_chat_id", chat_id)
    return jsonify({"ok": True})


@bp.route("/api/envio/config/gemini-modelo", methods=["POST"])
def salvar_modelo_gemini():
    modelo = str((request.json or {}).get("modelo", "")).strip()
    if modelo not in ia.MODELOS_GEMINI:
        return jsonify({"erro": f"modelo inválido. Use um de: {', '.join(ia.MODELOS_GEMINI)}"}), 400
    db.salvar_config("gemini_modelo", modelo)
    return jsonify({"ok": True, "modelo": modelo})


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------

@bp.route("/api/envio/whatsapp/estado")
def estado_whatsapp():
    try:
        return jsonify({"estado": mensageiros.estado_whatsapp()})
    except mensageiros.ErroEnvio as excecao:
        return jsonify({"estado": "indisponivel", "detalhe": str(excecao)})


@bp.route("/api/envio/whatsapp/conectar", methods=["POST"])
def conectar_whatsapp():
    try:
        qrcode = mensageiros.conectar_whatsapp()
    except mensageiros.ErroEnvio as excecao:
        return _erro(excecao)
    return jsonify({"conectado": qrcode is None, "qrcode": qrcode})


@bp.route("/api/envio/whatsapp/<canal>/<path:lead_ref>", methods=["POST"])
def enviar_whatsapp(canal, lead_ref):
    lead, erro = _validar_alvo(canal, lead_ref)
    if erro:
        return erro

    texto = str((request.json or {}).get("texto", "")).strip()
    if not texto:
        return jsonify({"erro": "a mensagem não pode ficar vazia"}), 400
    if len(texto) > MAX_CARACTERES_MENSAGEM_CONVERSA:
        return jsonify({"erro": "mensagem muito longa"}), 400

    telefone = lead.get("telefone") or lead.get("whatsapp_link")
    if not telefone:
        return jsonify({"erro": "este lead não tem telefone/WhatsApp"}), 400

    conexao = db.conectar()
    try:
        limite = _limite_diario()
        if _enviados_hoje(conexao) >= limite:
            return jsonify({
                "erro": f"limite diário de {limite} envios atingido. Isso protege seu número contra "
                        "bloqueio - continue amanhã ou ajuste o limite em Configurações."
            }), 429
    finally:
        conexao.close()

    try:
        id_externo = mensageiros.enviar_whatsapp(telefone, texto)
    except mensageiros.ErroEnvio as excecao:
        return _erro(excecao, 502)

    agora = _agora()
    conexao = db.conectar()
    try:
        chave = f"wa:{id_externo}" if id_externo else None
        _inserir_mensagem(conexao, canal, lead_ref, "vendedor", texto, agora, "app", chave)
        status_novo = None
        if canal == "maps" and lead.get("status") == "novo":
            status_novo = "contatado"
            conexao.execute(
                "UPDATE leads SET status = ?, atualizado_em = ? WHERE place_id = ?",
                (status_novo, agora, lead_ref),
            )
            conexao.execute(
                "INSERT INTO historico_status (place_id, status_anterior, status_novo, alterado_em) "
                "VALUES (?, ?, ?, ?)",
                (lead_ref, "novo", status_novo, agora),
            )
        conexao.commit()
        enviados = _enviados_hoje(conexao)
    finally:
        conexao.close()

    logger.info("whatsapp enviado para %s/%s via Evolution", canal, lead_ref)
    return jsonify({"ok": True, "status_novo": status_novo, "enviados_hoje": enviados,
                    "limite_diario": _limite_diario()})


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

@bp.route("/api/envio/telegram/detectar-chat", methods=["POST"])
def detectar_chat_telegram():
    try:
        chat_id, nome = mensageiros.descobrir_chat_telegram()
    except mensageiros.ErroEnvio as excecao:
        return _erro(excecao)
    db.salvar_config("telegram_chat_id", chat_id)
    return jsonify({"ok": True, "chat_id": chat_id, "nome": nome})


@bp.route("/api/envio/telegram/teste", methods=["POST"])
def testar_telegram():
    try:
        mensageiros.enviar_telegram("✅ ProspectOS conectado! Você vai receber os avisos por aqui.")
    except mensageiros.ErroEnvio as excecao:
        return _erro(excecao)
    return jsonify({"ok": True})


def montar_resumo_do_dia():
    """Texto curto com os follow-ups vencidos/de hoje e os leads novos de maior nota."""
    hoje = date.today().isoformat()
    encerram = sorted(STATUS_QUE_ENCERRAM_FOLLOWUP)
    marcadores = ",".join("?" for _ in encerram)
    conexao = db.conectar()
    try:
        followups = conexao.execute(
            f"SELECT nome, telefone FROM leads WHERE proximo_followup IS NOT NULL "
            f"AND substr(proximo_followup, 1, 10) <= ? AND status NOT IN ({marcadores}) "
            f"ORDER BY proximo_followup LIMIT 10",
            (hoje, *encerram),
        ).fetchall()
        novos = conexao.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'novo'"
        ).fetchone()[0]
        enviados = _enviados_hoje(conexao)
    finally:
        conexao.close()

    linhas = [f"📋 ProspectOS - resumo de {date.today().strftime('%d/%m')}", ""]
    if followups:
        linhas.append(f"🔁 {len(followups)} follow-up(s) pra hoje:")
        linhas += [f"• {f['nome']} - {f['telefone'] or 'sem telefone'}" for f in followups]
    else:
        linhas.append("🔁 Nenhum follow-up pendente hoje.")
    linhas += ["", f"🆕 {novos} lead(s) novo(s) esperando o primeiro contato.",
               f"📤 {enviados} mensagem(ns) enviada(s) pelo app hoje."]
    return "\n".join(linhas)


@bp.route("/api/envio/telegram/resumo", methods=["POST"])
def enviar_resumo_telegram():
    try:
        mensageiros.enviar_telegram(montar_resumo_do_dia())
    except mensageiros.ErroEnvio as excecao:
        return _erro(excecao)
    return jsonify({"ok": True})
