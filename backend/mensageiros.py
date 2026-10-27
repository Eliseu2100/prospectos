"""Clientes de envio de mensagens: WhatsApp (Evolution API) e Telegram (Bot API).

Como as peças se encaixam:
- WhatsApp: a Evolution API (open source, roda local via Docker) conecta o SEU
  número por QR code e expõe uma API HTTP de envio. O ProspectOS só fala HTTP
  com ela - nunca automatiza a janela do WhatsApp Web.
- Telegram: bot oficial (BotFather). Bot não pode iniciar conversa com quem
  nunca falou com ele, então o uso aqui é avisar VOCÊ (resumo do dia, teste),
  não abordar lead frio.

Nenhuma função aqui toca o banco de leads: só lê configuração e faz HTTP.
As regras de negócio (limite diário, registro no histórico) ficam em rotas_envio.py.
"""

import logging
import re

import requests

import db

logger = logging.getLogger(__name__)

TIMEOUT_HTTP_SEGUNDOS = 15
URL_API_TELEGRAM = "https://api.telegram.org"


class ErroEnvio(Exception):
    """Falha que já vem com mensagem amigável pro usuário final."""


# ---------------------------------------------------------------------------
# WhatsApp - Evolution API
# ---------------------------------------------------------------------------

def config_evolution():
    """Retorna (url_base, api_key, instancia) ou levanta ErroEnvio se faltar algo."""
    url = (db.obter_config("evolution_url") or "").strip().rstrip("/")
    chave = (db.obter_config("evolution_api_key") or "").strip()
    instancia = (db.obter_config("evolution_instancia") or "").strip()
    if not (url and chave and instancia):
        raise ErroEnvio(
            "WhatsApp não configurado. Preencha URL, chave e instância da Evolution API em Configurações."
        )
    return url, chave, instancia


def _evolution(metodo, caminho, corpo=None):
    url, chave, _ = config_evolution()
    try:
        resposta = requests.request(
            metodo, f"{url}{caminho}", json=corpo,
            headers={"apikey": chave}, timeout=TIMEOUT_HTTP_SEGUNDOS,
        )
    except requests.RequestException as erro:
        logger.warning("evolution inacessível em %s: %s", url, erro)
        raise ErroEnvio(
            "Não consegui falar com a Evolution API. Confira se o Docker está rodando "
            "(docker compose up -d na pasta evolution/) e se a URL está certa."
        ) from erro

    if resposta.status_code == 401:
        raise ErroEnvio("A Evolution API recusou a chave (401). Confira a chave em Configurações.")
    try:
        dados = resposta.json()
    except ValueError:
        dados = {}
    if resposta.status_code >= 400:
        logger.warning("evolution respondeu %s em %s: %s", resposta.status_code, caminho, dados)
        raise ErroEnvio(_mensagem_erro_evolution(resposta.status_code, dados))
    return dados


def _mensagem_erro_evolution(status, dados):
    texto = str(dados).lower()
    if "exists" in texto and "false" in texto:
        return "Esse número não tem WhatsApp."
    if status == 404:
        return "Instância não encontrada na Evolution API. Clique em 'Conectar' em Configurações para criá-la."
    return f"A Evolution API recusou o envio ({status})."


def estado_whatsapp():
    """'open' (conectado), 'connecting', 'close' ou 'inexistente'."""
    _, _, instancia = config_evolution()
    try:
        dados = _evolution("GET", f"/instance/connectionState/{instancia}")
    except ErroEnvio as erro:
        if "não encontrada" in str(erro):
            return "inexistente"
        raise
    return ((dados.get("instance") or {}).get("state")) or dados.get("state") or "close"


def conectar_whatsapp():
    """Cria a instância se ainda não existir e devolve o QR code (data URL base64)
    para escanear com o celular. Retorna None se já estiver conectado."""
    _, _, instancia = config_evolution()
    estado = estado_whatsapp()
    if estado == "open":
        return None
    if estado == "inexistente":
        dados = _evolution("POST", "/instance/create", {
            "instanceName": instancia,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
        })
        qrcode = (dados.get("qrcode") or {}).get("base64")
        if qrcode:
            return qrcode
    dados = _evolution("GET", f"/instance/connect/{instancia}")
    return dados.get("base64")


def numero_internacional(telefone):
    """Formato que a Evolution espera: só dígitos, com DDI 55."""
    digitos = re.sub(r"\D", "", telefone or "")
    if not digitos:
        return None
    if not digitos.startswith("55") or len(digitos) <= 11:
        digitos = "55" + digitos
    return digitos


def enviar_whatsapp(telefone, texto):
    _, _, instancia = config_evolution()
    numero = numero_internacional(telefone)
    if not numero:
        raise ErroEnvio("Este lead não tem telefone.")
    dados = _evolution("POST", f"/message/sendText/{instancia}", {"number": numero, "text": texto})
    return (dados.get("key") or {}).get("id")


# ---------------------------------------------------------------------------
# Telegram - Bot API oficial
# ---------------------------------------------------------------------------

def _token_telegram():
    token = (db.obter_config("telegram_bot_token") or "").strip()
    if not token:
        raise ErroEnvio("Bot do Telegram não configurado. Cole o token do @BotFather em Configurações.")
    return token


def _telegram(metodo_api, corpo=None):
    token = _token_telegram()
    try:
        resposta = requests.post(f"{URL_API_TELEGRAM}/bot{token}/{metodo_api}", json=corpo or {},
                                 timeout=TIMEOUT_HTTP_SEGUNDOS)
        dados = resposta.json()
    except (requests.RequestException, ValueError) as erro:
        raise ErroEnvio("Não consegui falar com o Telegram. Confira sua internet.") from erro
    if not dados.get("ok"):
        descricao = dados.get("description", "erro desconhecido")
        if resposta.status_code == 401:
            raise ErroEnvio("O Telegram recusou o token do bot. Confira em Configurações.")
        raise ErroEnvio(f"O Telegram recusou a mensagem: {descricao}")
    return dados.get("result")


def descobrir_chat_telegram():
    """Pega o chat de quem mandou a mensagem mais recente pro bot. O usuário
    manda /start pro bot e clica em 'Detectar' - sem precisar caçar o chat_id."""
    atualizacoes = _telegram("getUpdates") or []
    for atualizacao in reversed(atualizacoes):
        mensagem = atualizacao.get("message") or atualizacao.get("edited_message") or {}
        chat = mensagem.get("chat") or {}
        if chat.get("id"):
            return str(chat["id"]), chat.get("first_name") or chat.get("title") or ""
    raise ErroEnvio("Nenhuma mensagem encontrada. Mande /start para o seu bot no Telegram e tente de novo.")


def enviar_telegram(texto, chat_id=None):
    _token_telegram()
    chat_id = chat_id or db.obter_config("telegram_chat_id")
    if not chat_id:
        raise ErroEnvio("Chat do Telegram não definido. Mande /start pro bot e clique em 'Detectar chat'.")
    _telegram("sendMessage", {"chat_id": chat_id, "text": texto})
